import dataclasses
import io
import re
from urllib.parse import urlparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclasses.dataclass
class Difference:
    category: str
    severity: str
    element: str
    property: str
    value1: str
    value2: str
    description: str
    human_description: str
    section_name: str
    element_name: str
    navigation: str
    crop1_bytes: bytes
    crop2_bytes: bytes
    count: int = 1
    viewport: str = ""


@dataclasses.dataclass
class VisualDiffResult:
    diff_image: bytes
    diff_percentage: float
    match_percentage: float
    highlighted_image1: bytes
    highlighted_image2: bytes


@dataclasses.dataclass
class ComparisonResult:
    viewport: str
    differences: list
    visual_diff: VisualDiffResult
    match_percentage: float
    summary: dict


def _parse_px(value: str) -> float:
    match = re.search(r"([-\d.]+)", value or "0")
    return float(match.group(1)) if match else 0.0


def _normalize_color(color: str) -> str:
    return re.sub(r"\s+", "", (color or "").lower())


def _normalize_font(font: str) -> str:
    return re.sub(r'["\s]', "", (font or "").lower())


TAG_NAMES = {
    "h1": "Main Heading",
    "h2": "Section Heading",
    "h3": "Sub-Heading",
    "h4": "Small Heading",
    "h5": "Minor Heading",
    "h6": "Minor Heading",
    "p": "Text Paragraph",
    "span": "Text",
    "a": "Link",
    "button": "Button",
    "nav": "Navigation Menu",
    "header": "Header",
    "footer": "Footer",
    "section": "Section",
    "article": "Article",
    "main": "Main Content",
    "div": "Content Block",
    "ul": "List",
    "ol": "Numbered List",
    "li": "List Item",
    "img": "Image",
    "input": "Input Field",
    "textarea": "Text Input",
    "select": "Dropdown",
    "label": "Label",
    "form": "Form",
    "table": "Table",
    "th": "Table Header",
    "td": "Table Cell",
}


def humanize_element(tag: str, text: str) -> str:
    base_name = TAG_NAMES.get(tag, "Element")
    snippet = (text or "").strip()[:50]
    if snippet:
        return f'{base_name} ("{snippet}")'
    return base_name


def get_section_name(bounding_box: dict, sections: list) -> str:
    el_y = bounding_box.get("y", 0)
    el_center = el_y + bounding_box.get("height", 0) / 2

    for sec in sections:
        if sec.y_start <= el_center <= sec.y_end:
            return sec.name

    if el_y < 300:
        return "Top of Page"
    return "Page Content"


def get_navigation(section_name: str, element_name: str, url: str) -> str:
    steps = [f"Open {url}"]

    section_lower = section_name.lower()
    if "header" in section_lower or "top" in section_lower or "banner" in section_lower:
        steps.append("Look at the very top of the page")
    elif "footer" in section_lower or "bottom" in section_lower:
        steps.append("Scroll all the way down to the bottom of the page")
    elif "navigation" in section_lower or "menu" in section_lower:
        steps.append("Look at the navigation/menu bar")
    else:
        steps.append(f'Scroll to the "{section_name}" area')

    steps.append(f"Find the {element_name}")
    return " → ".join(steps)


PROPERTY_DESCRIPTIONS = {
    "font-family": ("font style", "The text font (typeface) is different"),
    "font-size": ("text size", "The text size is different"),
    "font-weight": ("text boldness", "The text boldness/thickness is different"),
    "font-style": ("text style", "The text style (italic/normal) is different"),
    "line-height": ("line spacing", "The spacing between lines of text is different"),
    "letter-spacing": ("letter spacing", "The spacing between individual letters is different"),
    "text-align": ("text alignment", "The text alignment (left/center/right) is different"),
    "color": ("text color", "The text color is different"),
    "margin": ("outer spacing", "The space around this element is different"),
    "padding": ("inner spacing", "The space inside this element is different"),
    "display": ("visibility/layout", "This element's layout type has changed"),
    "position": ("position on page", "This element has moved to a different position on the page"),
    "dimensions": ("size", "This element's size (width/height) has changed"),
    "missing-element": ("missing content", "This content is present on one page but missing on the other"),
    "extra-element": ("extra content", "This content appears on one page but not the other"),
    "text-content": ("text content", "The text content is different between the two pages"),
    "page-title": ("page title", "The browser tab title is different"),
    "missing-image": ("missing image", "An image is present on one page but missing on the other"),
    "extra-image": ("extra image", "An extra image appears on one page"),
    "aspect-ratio": ("image shape", "The image proportions (shape) have changed"),
}


def humanize_description(prop: str, element_name: str, value1: str, value2: str) -> str:
    _, base_desc = PROPERTY_DESCRIPTIONS.get(prop, (prop, f"The {prop} is different"))

    if prop == "font-size":
        px1, px2 = _parse_px(value1), _parse_px(value2)
        if px2 > px1:
            return f"{element_name}: The text is larger on Page 2 ({value1} vs {value2})"
        return f"{element_name}: The text is smaller on Page 2 ({value1} vs {value2})"

    if prop == "font-family":
        return f'{element_name}: Different font used — Page 1 uses "{value1[:40]}", Page 2 uses "{value2[:40]}"'

    if prop == "color":
        return f"{element_name}: The text color is different between the two pages"

    if prop == "position":
        return f"{element_name}: This element has shifted position on the page"

    if prop == "dimensions":
        return f"{element_name}: The size of this element is different — Page 1: {value1}, Page 2: {value2}"

    if prop == "missing-element":
        return f'{element_name}: This content exists on Page 1 but is MISSING on Page 2'

    if prop == "extra-element":
        return f'{element_name}: This content exists on Page 2 but is NOT on Page 1'

    if prop == "text-content":
        return f'{element_name}: The text content has changed between the two pages'

    if prop == "missing-image":
        return f"An image is visible on Page 1 but is MISSING on Page 2"

    if prop == "extra-image":
        return f"An extra image appears on Page 2 that is not on Page 1"

    if prop in ("margin", "padding"):
        return f"{element_name}: The spacing around/inside this element is different"

    return f"{element_name}: {base_desc}"


def annotate_crop(screenshot_bytes: bytes, bb: dict, color: str = "red", label: str = "") -> bytes:
    from scraper import crop_region

    padding = 40
    x, y, w, h = bb.get("x", 0), bb.get("y", 0), bb.get("width", 100), bb.get("height", 50)
    w = max(w, 1)
    h = max(h, 1)
    crop = crop_region(screenshot_bytes, x, y, w, h, padding=padding)

    img = Image.open(io.BytesIO(crop))
    if img.width < 1 or img.height < 1:
        return screenshot_bytes
    draw = ImageDraw.Draw(img)

    box_x = min(padding, img.width - 2)
    box_y = min(padding, img.height - 2)
    box_x2 = min(int(padding + w), img.width - 1)
    box_y2 = min(int(padding + h), img.height - 1)

    for offset in range(3):
        draw.rectangle(
            [box_x - offset, box_y - offset, box_x2 + offset, box_y2 + offset],
            outline=color,
        )

    if label:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except (OSError, IOError):
            font = ImageFont.load_default()
        text_bb = draw.textbbox((0, 0), label, font=font)
        tw = text_bb[2] - text_bb[0]
        th = text_bb[3] - text_bb[1]
        label_y = max(0, box_y - th - 6)
        draw.rectangle([box_x, label_y, box_x + tw + 8, label_y + th + 4], fill=color)
        draw.text((box_x + 4, label_y + 2), label, fill="white", font=font)

    max_crop_width = 300
    if img.width > max_crop_width:
        ratio = max_crop_width / img.width
        new_h = max(1, int(img.height * ratio))
        img = img.resize((max_crop_width, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=60)
    return buf.getvalue()


def match_elements(elements1, elements2):
    matched = []
    used2 = set()

    selector_map2 = {}
    for i, el in enumerate(elements2):
        selector_map2.setdefault(el.selector, []).append(i)

    for el1 in elements1:
        best_idx = None
        if el1.selector in selector_map2:
            for idx in selector_map2[el1.selector]:
                if idx not in used2:
                    best_idx = idx
                    break

        if best_idx is None:
            for i, el2 in enumerate(elements2):
                if i not in used2 and el1.tag == el2.tag and el1.text and el1.text == el2.text:
                    best_idx = i
                    break

        if best_idx is not None:
            matched.append((el1, elements2[best_idx]))
            used2.add(best_idx)
        else:
            matched.append((el1, None))

    for i, el2 in enumerate(elements2):
        if i not in used2:
            matched.append((None, el2))

    return matched


SKIP_TAGS = {"div", "span", "li", "ul", "ol", "td", "th", "form", "section", "article", "main"}

IMPORTANT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "button", "img", "input", "nav", "header", "footer", "a"}


def _is_meaningful(tag: str, prop: str, severity: str, text: str = "") -> bool:
    if severity == "critical":
        return True
    if tag in SKIP_TAGS and severity == "minor":
        return False
    if tag in SKIP_TAGS and prop in ("margin", "padding", "position", "dimensions"):
        return False
    if not (text or "").strip() and severity == "minor":
        return False
    return True


def compare_typography(elements1, elements2, screenshot1, screenshot2, sections) -> list:
    diffs = []
    matched = match_elements(elements1, elements2)

    typo_props = [
        ("font_family", "font-family"),
        ("font_size", "font-size"),
        ("font_weight", "font-weight"),
        ("font_style", "font-style"),
        ("line_height", "line-height"),
        ("letter_spacing", "letter-spacing"),
        ("text_align", "text-align"),
        ("color", "color"),
    ]

    for el1, el2 in matched:
        if el1 is None or el2 is None:
            continue

        for attr, prop_name in typo_props:
            v1 = getattr(el1, attr, "")
            v2 = getattr(el2, attr, "")

            if prop_name == "color":
                v1_norm, v2_norm = _normalize_color(v1), _normalize_color(v2)
            elif prop_name == "font-family":
                v1_norm, v2_norm = _normalize_font(v1), _normalize_font(v2)
            else:
                v1_norm, v2_norm = (v1 or "").strip(), (v2 or "").strip()

            if v1_norm == v2_norm:
                continue

            severity = _typography_severity(prop_name, v1, v2, el1.tag)
            if not _is_meaningful(el1.tag, prop_name, severity, el1.text):
                continue

            element_name = humanize_element(el1.tag, el1.text)
            section_name = get_section_name(el1.bounding_box, sections)
            human_desc = humanize_description(prop_name, element_name, v1, v2)

            crop1 = annotate_crop(screenshot1, el1.bounding_box, color="red", label="Page 1")
            crop2 = annotate_crop(screenshot2, el2.bounding_box, color="blue", label="Page 2")

            diffs.append(Difference(
                category="Typography (Fonts & Text Style)",
                severity=severity,
                element=el1.selector,
                property=prop_name,
                value1=v1,
                value2=v2,
                description=f"{prop_name} changed on <{el1.tag}>",
                human_description=human_desc,
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1,
                crop2_bytes=crop2,
            ))

    return diffs


def _typography_severity(prop, v1, v2, tag):
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    if prop == "font-family":
        return "critical" if tag in heading_tags else "major"
    if prop == "font-size":
        diff = abs(_parse_px(v1) - _parse_px(v2))
        return "major" if diff > 4 else "minor"
    if prop == "color":
        return "major"
    if prop == "font-weight":
        return "major" if tag in heading_tags else "minor"
    return "minor"


def compare_layout(elements1, elements2, screenshot1, screenshot2, sections) -> list:
    diffs = []
    matched = match_elements(elements1, elements2)

    for el1, el2 in matched:
        if el1 is None or el2 is None:
            continue

        for attr, prop_name in [("margin", "margin"), ("padding", "padding")]:
            v1 = getattr(el1, attr, "")
            v2 = getattr(el2, attr, "")
            if (v1 or "").strip() != (v2 or "").strip():
                parts1 = (v1 or "0").split()
                parts2 = (v2 or "0").split()
                min_len = min(len(parts1), len(parts2))
                if min_len == 0:
                    continue
                max_diff = max(abs(_parse_px(parts1[i]) - _parse_px(parts2[i])) for i in range(min_len))
                severity = "major" if max_diff > 10 else "minor"
                if not _is_meaningful(el1.tag, prop_name, severity, el1.text):
                    continue

                element_name = humanize_element(el1.tag, el1.text)
                section_name = get_section_name(el1.bounding_box, sections)
                human_desc = humanize_description(prop_name, element_name, v1, v2)
                crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "Page 1")
                crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "Page 2")

                diffs.append(Difference(
                    category="Layout & Spacing",
                    severity=severity, element=el1.selector,
                    property=prop_name, value1=v1, value2=v2,
                    description=f"{prop_name} changed on <{el1.tag}>",
                    human_description=human_desc,
                    section_name=section_name,
                    element_name=element_name,
                    navigation="",
                    crop1_bytes=crop1, crop2_bytes=crop2,
                ))

        if el1.display != el2.display:
            element_name = humanize_element(el1.tag, el1.text)
            section_name = get_section_name(el1.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "Page 1")
            crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "Page 2")
            diffs.append(Difference(
                category="Layout & Spacing",
                severity="critical", element=el1.selector,
                property="display", value1=el1.display, value2=el2.display,
                description=f"display changed on <{el1.tag}>",
                human_description=f"{element_name}: The way this element is displayed has changed — it may look completely different",
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))

        bb1, bb2 = el1.bounding_box, el2.bounding_box
        dx = abs(bb1.get("x", 0) - bb2.get("x", 0))
        dy = abs(bb1.get("y", 0) - bb2.get("y", 0))
        shift = max(dx, dy)
        if shift > 10:
            severity = "critical" if shift > 30 else "major"
            if not _is_meaningful(el1.tag, "position", severity, el1.text):
                continue
            element_name = humanize_element(el1.tag, el1.text)
            section_name = get_section_name(el1.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "Page 1")
            crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "Page 2")
            diffs.append(Difference(
                category="Layout & Spacing",
                severity=severity, element=el1.selector,
                property="position",
                value1=f"x={bb1.get('x',0):.0f}, y={bb1.get('y',0):.0f}",
                value2=f"x={bb2.get('x',0):.0f}, y={bb2.get('y',0):.0f}",
                description=f"Position shifted {shift:.0f}px",
                human_description=f"{element_name}: This element has moved {shift:.0f} pixels from its original position",
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))

        dw = abs(bb1.get("width", 0) - bb2.get("width", 0))
        dh = abs(bb1.get("height", 0) - bb2.get("height", 0))
        if dw > 15 or dh > 15:
            severity = "major" if max(dw, dh) > 40 else "minor"
            if not _is_meaningful(el1.tag, "dimensions", severity, el1.text):
                continue
            element_name = humanize_element(el1.tag, el1.text)
            section_name = get_section_name(el1.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "Page 1")
            crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "Page 2")
            diffs.append(Difference(
                category="Layout & Spacing",
                severity=severity, element=el1.selector,
                property="dimensions",
                value1=f"{bb1.get('width',0):.0f}x{bb1.get('height',0):.0f}",
                value2=f"{bb2.get('width',0):.0f}x{bb2.get('height',0):.0f}",
                description=f"Size changed on <{el1.tag}>",
                human_description=humanize_description("dimensions", element_name,
                    f"{bb1.get('width',0):.0f}x{bb1.get('height',0):.0f}",
                    f"{bb2.get('width',0):.0f}x{bb2.get('height',0):.0f}"),
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))

    return diffs


def compare_content(page_data1, page_data2, screenshot1, screenshot2, sections) -> list:
    diffs = []
    matched = match_elements(page_data1.elements, page_data2.elements)

    for el1, el2 in matched:
        if el1 is not None and el2 is None:
            text = (el1.text or "").strip()
            if el1.tag in SKIP_TAGS:
                continue
            if not text and el1.tag not in IMPORTANT_TAGS:
                continue
            if len(text) < 3 and el1.tag not in IMPORTANT_TAGS:
                continue
            severity = "critical" if el1.tag in {"h1", "h2", "h3", "button", "nav", "header"} else "major"
            element_name = humanize_element(el1.tag, el1.text)
            section_name = get_section_name(el1.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "EXISTS on Page 1")
            crop2 = annotate_crop(screenshot2, el1.bounding_box, "blue", "MISSING HERE")
            diffs.append(Difference(
                category="Content",
                severity=severity,
                element=el1.selector, property="missing-element",
                value1=f"Present", value2="MISSING",
                description=f"<{el1.tag}> missing from page 2",
                human_description=humanize_description("missing-element", element_name, "", ""),
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))
        elif el1 is None and el2 is not None:
            text = (el2.text or "").strip()
            if el2.tag in SKIP_TAGS:
                continue
            if not text and el2.tag not in IMPORTANT_TAGS:
                continue
            if len(text) < 3 and el2.tag not in IMPORTANT_TAGS:
                continue
            severity = "major" if el2.tag in {"h1", "h2", "h3", "button", "nav", "header"} else "minor"
            element_name = humanize_element(el2.tag, el2.text)
            section_name = get_section_name(el2.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, el2.bounding_box, "red", "NOT HERE")
            crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "EXISTS on Page 2")
            diffs.append(Difference(
                category="Content",
                severity=severity,
                element=el2.selector, property="extra-element",
                value1="NOT present", value2="Present",
                description=f"Extra <{el2.tag}> in page 2",
                human_description=humanize_description("extra-element", element_name, "", ""),
                section_name=section_name,
                element_name=element_name,
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))
        elif el1 is not None and el2 is not None:
            if el1.text and el2.text and el1.text != el2.text:
                if el1.tag in SKIP_TAGS:
                    continue
                if len((el1.text or "").strip()) < 5 and el1.tag not in IMPORTANT_TAGS:
                    continue
                severity = "major" if el1.tag in {"h1", "h2", "h3", "h4", "button"} else "minor"
                element_name = humanize_element(el1.tag, el1.text)
                section_name = get_section_name(el1.bounding_box, sections)
                crop1 = annotate_crop(screenshot1, el1.bounding_box, "red", "Page 1")
                crop2 = annotate_crop(screenshot2, el2.bounding_box, "blue", "Page 2")
                diffs.append(Difference(
                    category="Content",
                    severity=severity,
                    element=el1.selector, property="text-content",
                    value1=el1.text[:100], value2=el2.text[:100],
                    description=f"Text changed on <{el1.tag}>",
                    human_description=humanize_description("text-content", element_name, el1.text[:80], el2.text[:80]),
                    section_name=section_name,
                    element_name=element_name,
                    navigation="",
                    crop1_bytes=crop1, crop2_bytes=crop2,
                ))

    if page_data1.page_title != page_data2.page_title:
        top_bb = {"x": 0, "y": 0, "width": 400, "height": 60}
        title_crop1 = annotate_crop(screenshot1, top_bb, "red", "Page 1 Title Area")
        title_crop2 = annotate_crop(screenshot2, top_bb, "blue", "Page 2 Title Area")
        diffs.append(Difference(
            category="Content",
            severity="major",
            element="<title>", property="page-title",
            value1=page_data1.page_title, value2=page_data2.page_title,
            description="Page title changed",
            human_description=f'The browser tab title is different: Page 1 shows "{page_data1.page_title}", Page 2 shows "{page_data2.page_title}"',
            section_name="Browser Tab",
            element_name="Page Title",
            navigation="Look at the browser tab at the top of your browser window",
            crop1_bytes=title_crop1, crop2_bytes=title_crop2,
        ))

    return diffs


def compare_images(images1, images2, screenshot1, screenshot2, sections) -> list:
    diffs = []

    def normalize_src(src):
        return urlparse(src).path

    src_map1 = {normalize_src(img.src): img for img in images1}
    src_map2 = {normalize_src(img.src): img for img in images2}

    all_srcs = set(src_map1.keys()) | set(src_map2.keys())

    for src in all_srcs:
        img1 = src_map1.get(src)
        img2 = src_map2.get(src)

        if img1 and not img2:
            section_name = get_section_name(img1.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, img1.bounding_box, "red", "MISSING on Page 2")
            crop2 = annotate_crop(screenshot2, img1.bounding_box, "blue", "MISSING HERE")
            diffs.append(Difference(
                category="Images",
                severity="critical",
                element=f"Image", property="missing-image",
                value1="Visible", value2="MISSING",
                description=f"Image missing from page 2",
                human_description=f"An image ({img1.alt or 'no description'}) is visible on Page 1 but is MISSING on Page 2",
                section_name=section_name,
                element_name=f"Image: {img1.alt or src.split('/')[-1][:30]}",
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))
        elif not img1 and img2:
            section_name = get_section_name(img2.bounding_box, sections)
            crop1 = annotate_crop(screenshot1, img2.bounding_box, "red", "NOT HERE")
            crop2 = annotate_crop(screenshot2, img2.bounding_box, "blue", "EXTRA on Page 2")
            diffs.append(Difference(
                category="Images",
                severity="major",
                element=f"Image", property="extra-image",
                value1="Not present", value2="Visible",
                description=f"Extra image in page 2",
                human_description=f"An extra image ({img2.alt or 'no description'}) appears on Page 2 that is not on Page 1",
                section_name=section_name,
                element_name=f"Image: {img2.alt or src.split('/')[-1][:30]}",
                navigation="",
                crop1_bytes=crop1, crop2_bytes=crop2,
            ))
        elif img1 and img2:
            section_name = get_section_name(img1.bounding_box, sections)
            w_diff = abs(img1.displayed_width - img2.displayed_width)
            h_diff = abs(img1.displayed_height - img2.displayed_height)
            if w_diff > 5 or h_diff > 5:
                pct = max(
                    w_diff / max(img1.displayed_width, 1) * 100,
                    h_diff / max(img1.displayed_height, 1) * 100,
                )
                severity = "major" if pct > 20 else "minor"
                crop1 = annotate_crop(screenshot1, img1.bounding_box, "red", "Page 1")
                crop2 = annotate_crop(screenshot2, img2.bounding_box, "blue", "Page 2")
                diffs.append(Difference(
                    category="Images",
                    severity=severity,
                    element="Image", property="dimensions",
                    value1=f"{img1.displayed_width:.0f}x{img1.displayed_height:.0f}",
                    value2=f"{img2.displayed_width:.0f}x{img2.displayed_height:.0f}",
                    description=f"Image dimensions changed",
                    human_description=f"Image ({img1.alt or 'image'}) has a different size — Page 1: {img1.displayed_width:.0f}x{img1.displayed_height:.0f}px, Page 2: {img2.displayed_width:.0f}x{img2.displayed_height:.0f}px",
                    section_name=section_name,
                    element_name=f"Image: {img1.alt or src.split('/')[-1][:30]}",
                    navigation="",
                    crop1_bytes=crop1, crop2_bytes=crop2,
                ))

            if img1.aspect_ratio > 0 and img2.aspect_ratio > 0:
                ar_diff = abs(img1.aspect_ratio - img2.aspect_ratio)
                if ar_diff > 0.05:
                    crop1 = annotate_crop(screenshot1, img1.bounding_box, "red", "Page 1")
                    crop2 = annotate_crop(screenshot2, img2.bounding_box, "blue", "Page 2")
                    diffs.append(Difference(
                        category="Images",
                        severity="major",
                        element="Image", property="aspect-ratio",
                        value1=f"{img1.aspect_ratio:.2f}", value2=f"{img2.aspect_ratio:.2f}",
                        description="Image aspect ratio changed",
                        human_description=f"Image ({img1.alt or 'image'}) looks stretched or squished — its proportions have changed",
                        section_name=section_name,
                        element_name=f"Image: {img1.alt or src.split('/')[-1][:30]}",
                        navigation="",
                        crop1_bytes=crop1, crop2_bytes=crop2,
                    ))

    return diffs


def compare_visual(screenshot1: bytes, screenshot2: bytes, threshold: int = 30) -> VisualDiffResult:
    img1 = Image.open(io.BytesIO(screenshot1)).convert("RGB")
    img2 = Image.open(io.BytesIO(screenshot2)).convert("RGB")

    cap = 30000
    if img1.height > cap:
        img1 = img1.crop((0, 0, img1.width, cap))
    if img2.height > cap:
        img2 = img2.crop((0, 0, img2.width, cap))

    max_w = max(img1.width, img2.width)
    max_h = max(img1.height, img2.height)

    def pad_image(img, w, h):
        if img.width == w and img.height == h:
            return img
        padded = Image.new("RGB", (w, h), (255, 255, 255))
        padded.paste(img, (0, 0))
        return padded

    img1 = pad_image(img1, max_w, max_h)
    img2 = pad_image(img2, max_w, max_h)

    arr1 = np.array(img1, dtype=np.int16)
    arr2 = np.array(img2, dtype=np.int16)

    diff_arr = np.abs(arr1 - arr2)
    mask = np.max(diff_arr, axis=2) > threshold

    total_pixels = mask.size
    diff_pixels = int(np.count_nonzero(mask))
    diff_percentage = (diff_pixels / total_pixels) * 100 if total_pixels > 0 else 0

    blend = Image.blend(img1, img2, 0.5)
    diff_overlay = blend.copy()
    diff_overlay_arr = np.array(diff_overlay)
    diff_overlay_arr[mask] = [255, 0, 100]
    diff_image = Image.fromarray(diff_overlay_arr.astype(np.uint8))

    regions = _find_diff_regions(mask)

    hl1 = img1.copy()
    hl2 = img2.copy()
    draw1 = ImageDraw.Draw(hl1)
    draw2 = ImageDraw.Draw(hl2)
    for (x1, y1, x2, y2) in regions:
        draw1.rectangle([x1, y1, x2, y2], outline="red", width=3)
        draw2.rectangle([x1, y1, x2, y2], outline="red", width=3)

    return VisualDiffResult(
        diff_image=_image_to_bytes(diff_image),
        diff_percentage=round(diff_percentage, 2),
        match_percentage=round(100 - diff_percentage, 2),
        highlighted_image1=_image_to_bytes(hl1),
        highlighted_image2=_image_to_bytes(hl2),
    )


def _find_diff_regions(mask, block_size=50):
    regions = []
    h, w = mask.shape
    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            block = mask[y:min(y + block_size, h), x:min(x + block_size, w)]
            if np.any(block):
                regions.append((x, y, min(x + block_size, w), min(y + block_size, h)))
    if not regions:
        return regions
    merged = []
    regions.sort(key=lambda r: (r[1], r[0]))
    current = list(regions[0])
    for r in regions[1:]:
        if r[0] <= current[2] + block_size and r[1] <= current[3] + block_size:
            current[2] = max(current[2], r[2])
            current[3] = max(current[3], r[3])
        else:
            merged.append(tuple(current))
            current = list(r)
    merged.append(tuple(current))
    return merged


def _image_to_bytes(img: Image.Image) -> bytes:
    max_width = 1200
    max_height = 60000
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * ratio))), Image.LANCZOS)
    if img.height > max_height:
        img = img.crop((0, 0, img.width, max_height))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=55)
    return buf.getvalue()


def calculate_match_percentage(visual_diff: VisualDiffResult, diffs: list, total_elements: int) -> float:
    visual_match = visual_diff.match_percentage * 0.4
    cats = {"Typography (Fonts & Text Style)": 0, "Layout & Spacing": 0, "Content": 0, "Images": 0}
    for d in diffs:
        if d.category in cats:
            weight = {"critical": 3, "major": 2, "minor": 1}.get(d.severity, 1)
            cats[d.category] += weight
    max_issues = max(total_elements, 1)
    typo_match = max(0, 100 - (cats["Typography (Fonts & Text Style)"] / max_issues * 100)) * 0.2
    layout_match = max(0, 100 - (cats["Layout & Spacing"] / max_issues * 100)) * 0.2
    content_match = max(0, 100 - (cats["Content"] / max_issues * 100)) * 0.1
    image_match = max(0, 100 - (cats["Images"] / max_issues * 100)) * 0.1
    return round(visual_match + typo_match + layout_match + content_match + image_match, 1)


def build_summary(diffs: list) -> dict:
    summary = {}
    for d in diffs:
        cat = d.category
        sev = d.severity
        if cat not in summary:
            summary[cat] = {"critical": 0, "major": 0, "minor": 0, "total": 0}
        summary[cat][sev] += 1
        summary[cat]["total"] += 1
    return summary


def deduplicate_diffs(diffs: list) -> list:
    severity_rank = {"critical": 0, "major": 1, "minor": 2}

    seen = set()
    unique = []
    for d in diffs:
        key = (d.element, d.property)
        if key not in seen:
            seen.add(key)
            unique.append(d)

    element_groups = {}
    for d in unique:
        element_groups.setdefault(d.element, []).append(d)

    element_merged = []
    for el_key, group in element_groups.items():
        if len(group) == 1:
            element_merged.append(group[0])
            continue
        group.sort(key=lambda x: severity_rank.get(x.severity, 3))
        best = group[0]
        descs = [g.human_description for g in group]
        cats = set(g.category for g in group)
        combined_desc = descs[0]
        extras = [d for d in descs[1:] if d != descs[0]]
        if extras:
            combined_desc += " | Also: " + "; ".join(extras[:2])
        element_merged.append(Difference(
            category=", ".join(sorted(cats)) if len(cats) > 1 else best.category,
            severity=best.severity, element=best.element,
            property=best.property, value1=best.value1, value2=best.value2,
            description=best.description, human_description=combined_desc,
            section_name=best.section_name, element_name=best.element_name,
            navigation=best.navigation,
            crop1_bytes=best.crop1_bytes, crop2_bytes=best.crop2_bytes, count=1,
        ))

    def _tag_from_name(name):
        return name.split("(")[0].strip().lower() if name else "element"

    pattern_groups = {}
    for d in element_merged:
        key = (d.property, _tag_from_name(d.element_name))
        pattern_groups.setdefault(key, []).append(d)

    final = []
    for (prop, tag_name), group in pattern_groups.items():
        if len(group) <= 2:
            final.extend(group)
            continue
        group.sort(key=lambda x: severity_rank.get(x.severity, 3))
        best = group[0]
        count = len(group)
        tag_display = tag_name.title()

        desc_map = {
            "missing-element": f"{count} {tag_display} items are missing on Page 2",
            "extra-element": f"{count} extra {tag_display} items appear on Page 2",
            "position": f"{count} {tag_display} elements have shifted position",
            "dimensions": f"{count} {tag_display} elements have changed size",
            "font-size": f"{count} {tag_display} elements have different text sizes",
            "color": f"{count} {tag_display} elements have different colors",
            "margin": f"{count} {tag_display} elements have different spacing",
            "padding": f"{count} {tag_display} elements have different inner spacing",
        }
        summary_desc = desc_map.get(prop, f"{count} {tag_display} elements have {prop} differences")

        final.append(Difference(
            category=best.category, severity=best.severity,
            element=best.element, property=best.property,
            value1=best.value1, value2=best.value2,
            description=best.description, human_description=summary_desc,
            section_name=best.section_name,
            element_name=f"{tag_display} ({count} items)",
            navigation=best.navigation,
            crop1_bytes=best.crop1_bytes, crop2_bytes=best.crop2_bytes,
            count=count,
        ))

    final.sort(key=lambda d: (severity_rank.get(d.severity, 3), -d.count))
    return final


def analyze(page_data1, page_data2, threshold=30, top_issues=50) -> ComparisonResult:
    sections = page_data1.sections or page_data2.sections or []
    url1 = page_data1.url

    typo_diffs = compare_typography(page_data1.elements, page_data2.elements, page_data1.screenshot, page_data2.screenshot, sections)
    layout_diffs = compare_layout(page_data1.elements, page_data2.elements, page_data1.screenshot, page_data2.screenshot, sections)
    content_diffs = compare_content(page_data1, page_data2, page_data1.screenshot, page_data2.screenshot, sections)
    image_diffs = compare_images(page_data1.images, page_data2.images, page_data1.screenshot, page_data2.screenshot, sections)
    visual_diff = compare_visual(page_data1.screenshot, page_data2.screenshot, threshold)

    all_diffs = typo_diffs + layout_diffs + content_diffs + image_diffs

    for d in all_diffs:
        if not d.navigation:
            d.navigation = get_navigation(d.section_name, d.element_name, url1)

    all_diffs = deduplicate_diffs(all_diffs)

    total_elements = max(len(page_data1.elements), len(page_data2.elements))
    match_pct = calculate_match_percentage(visual_diff, all_diffs, total_elements)

    summary = build_summary(all_diffs)

    if top_issues and len(all_diffs) > top_issues:
        all_diffs = all_diffs[:top_issues]

    return ComparisonResult(
        viewport=page_data1.viewport,
        differences=all_diffs,
        visual_diff=visual_diff,
        match_percentage=match_pct,
        summary=summary,
    )
