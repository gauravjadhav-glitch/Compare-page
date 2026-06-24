import re
from analyzer import Difference
from scraper import PageData, crop_region


def run_accessibility_checks(page_data: PageData, page_label: str = "Page") -> list:
    diffs = []
    diffs.extend(_check_color_contrast(page_data, page_label))
    diffs.extend(_check_missing_alt_text(page_data, page_label))
    diffs.extend(_check_aria_labels(page_data, page_label))
    diffs.extend(_check_tab_order(page_data, page_label))
    return diffs


def _parse_rgb(color_str: str):
    m = re.match(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str or "")
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def _linearize(c: int) -> float:
    s = c / 255.0
    if s <= 0.04045:
        return s / 12.92
    return ((s + 0.055) / 1.055) ** 2.4


def _relative_luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _contrast_ratio(rgb1: tuple, rgb2: tuple) -> float:
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_px(value: str) -> float:
    m = re.match(r'([\d.]+)', value or "")
    return float(m.group(1)) if m else 0.0


def _is_large_text(font_size: str, font_weight: str) -> bool:
    size = _parse_px(font_size)
    weight = 400
    try:
        weight = int(font_weight)
    except (ValueError, TypeError):
        if font_weight == "bold":
            weight = 700
    return size >= 18 or (size >= 14 and weight >= 700)


def _check_color_contrast(page_data: PageData, page_label: str) -> list:
    diffs = []
    text_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "button", "label", "li", "td", "th"}
    checked = set()

    for el in page_data.elements:
        if el.tag not in text_tags or not el.text.strip():
            continue

        fg = _parse_rgb(el.color)
        bg = _parse_rgb(el.background_color)
        if not fg or not bg:
            continue

        if bg == (0, 0, 0) and el.background_color and "rgba(0, 0, 0, 0)" in el.background_color:
            bg = (255, 255, 255)

        key = (fg, bg, el.tag)
        if key in checked:
            continue
        checked.add(key)

        ratio = _contrast_ratio(fg, bg)
        large = _is_large_text(el.font_size, el.font_weight)
        aa_threshold = 3.0 if large else 4.5
        aaa_threshold = 4.5 if large else 7.0

        if ratio < aa_threshold:
            important = el.tag in ("h1", "h2", "h3", "button", "a", "label")
            severity = "critical" if important else "major"

            crop = b""
            try:
                bb = el.bounding_box
                crop = crop_region(page_data.screenshot, bb["x"], bb["y"], bb["width"], bb["height"])
            except Exception:
                pass

            diffs.append(Difference(
                category="Accessibility (Contrast)",
                severity=severity,
                element=el.selector,
                property="contrast-fail-aa",
                value1=f"Ratio {ratio:.1f}:1",
                value2=f"Required {aa_threshold}:1 (WCAG AA)",
                description=f"Color contrast {ratio:.1f}:1 fails WCAG AA ({aa_threshold}:1 needed)",
                human_description=f"[{page_label}] Text is hard to read: contrast ratio is {ratio:.1f}:1 but needs at least {aa_threshold}:1. Text color: {el.color}, Background: {el.background_color}",
                section_name=_find_section(page_data.sections, el.bounding_box.get("y", 0)),
                element_name=f"{el.tag} \"{el.text[:40]}\"",
                navigation=f"Look for the text \"{el.text[:60]}\" on the page",
                crop1_bytes=crop,
                crop2_bytes=b"",
            ))
        elif ratio < aaa_threshold:
            diffs.append(Difference(
                category="Accessibility (Contrast)",
                severity="minor",
                element=el.selector,
                property="contrast-fail-aaa",
                value1=f"Ratio {ratio:.1f}:1",
                value2=f"Required {aaa_threshold}:1 (WCAG AAA)",
                description=f"Color contrast {ratio:.1f}:1 passes AA but fails AAA ({aaa_threshold}:1)",
                human_description=f"[{page_label}] Text contrast could be improved: {ratio:.1f}:1 (WCAG AAA needs {aaa_threshold}:1)",
                section_name=_find_section(page_data.sections, el.bounding_box.get("y", 0)),
                element_name=f"{el.tag} \"{el.text[:40]}\"",
                navigation=f"Look for the text \"{el.text[:60]}\" on the page",
                crop1_bytes=b"",
                crop2_bytes=b"",
            ))

    return diffs


def _check_missing_alt_text(page_data: PageData, page_label: str) -> list:
    diffs = []

    for img in (page_data.images or []):
        if img.alt and img.alt.strip():
            continue
        bb = img.bounding_box
        if bb.get("width", 0) < 20 or bb.get("height", 0) < 20:
            continue

        crop = b""
        try:
            crop = crop_region(page_data.screenshot, bb["x"], bb["y"], bb["width"], bb["height"])
        except Exception:
            pass

        diffs.append(Difference(
            category="Accessibility (Alt Text)",
            severity="major",
            element=img.src[:100],
            property="missing-alt-text",
            value1="(empty)",
            value2="Needs descriptive alt text",
            description=f"Image missing alt text: {img.src[:80]}",
            human_description=f"[{page_label}] Image has no alt text. Screen readers cannot describe this image to visually impaired users.",
            section_name=_find_section(page_data.sections, bb.get("y", 0)),
            element_name=f"img ({int(bb.get('width', 0))}x{int(bb.get('height', 0))}px)",
            navigation=f"Find this image on the page at approximately {int(bb.get('y', 0))}px from top",
            crop1_bytes=crop,
            crop2_bytes=b"",
        ))

    return diffs


def _check_aria_labels(page_data: PageData, page_label: str) -> list:
    diffs = []
    interactive_tags = {"button", "a", "input", "select", "textarea"}

    for el in page_data.elements:
        if el.tag not in interactive_tags:
            continue
        has_text = bool(el.text.strip())
        has_aria = bool(el.aria_label.strip()) if el.aria_label else False
        if has_text or has_aria:
            continue

        crop = b""
        try:
            bb = el.bounding_box
            crop = crop_region(page_data.screenshot, bb["x"], bb["y"], bb["width"], bb["height"])
        except Exception:
            pass

        diffs.append(Difference(
            category="Accessibility (ARIA)",
            severity="major",
            element=el.selector,
            property="missing-aria-label",
            value1="No label or aria-label",
            value2="Needs accessible label",
            description=f"Interactive {el.tag} element has no visible text or aria-label",
            human_description=f"[{page_label}] This {el.tag} has no text label. Users with screen readers won't know what it does.",
            section_name=_find_section(page_data.sections, el.bounding_box.get("y", 0)),
            element_name=f"{el.tag} ({el.selector[:50]})",
            navigation=f"Find this {el.tag} element using CSS selector: {el.selector[:80]}",
            crop1_bytes=crop,
            crop2_bytes=b"",
        ))

    return diffs


def _check_tab_order(page_data: PageData, page_label: str) -> list:
    diffs = []
    important_tags = {"button", "a", "input", "select", "textarea"}

    for el in page_data.elements:
        if not el.tab_index:
            continue

        try:
            idx = int(el.tab_index)
        except (ValueError, TypeError):
            continue

        if idx > 0:
            diffs.append(Difference(
                category="Accessibility (Tab Order)",
                severity="minor",
                element=el.selector,
                property="tab-order-issue",
                value1=f"tabindex={idx}",
                value2="Should use tabindex=0 or natural DOM order",
                description=f"Positive tabindex overrides natural tab order",
                human_description=f"[{page_label}] Element has tabindex={idx} which overrides natural keyboard navigation order. Use tabindex=0 instead.",
                section_name=_find_section(page_data.sections, el.bounding_box.get("y", 0)),
                element_name=f"{el.tag} \"{el.text[:40]}\"",
                navigation=f"Tab through the page to find this element: {el.text[:60]}",
                crop1_bytes=b"",
                crop2_bytes=b"",
            ))
        elif idx == -1 and el.tag in important_tags:
            diffs.append(Difference(
                category="Accessibility (Tab Order)",
                severity="major",
                element=el.selector,
                property="tab-order-issue",
                value1="tabindex=-1 (removed from tab order)",
                value2="Interactive elements should be keyboard accessible",
                description=f"Important {el.tag} removed from keyboard tab order",
                human_description=f"[{page_label}] This {el.tag} cannot be reached by keyboard. Users who can't use a mouse won't be able to interact with it.",
                section_name=_find_section(page_data.sections, el.bounding_box.get("y", 0)),
                element_name=f"{el.tag} \"{el.text[:40]}\"",
                navigation=f"Try tabbing through the page. This element will be skipped: {el.text[:60]}",
                crop1_bytes=b"",
                crop2_bytes=b"",
            ))

    return diffs


def _find_section(sections: list, y_pos: float) -> str:
    for sec in sections:
        if sec.y_start <= y_pos <= sec.y_end:
            return sec.name
    return "Page"
