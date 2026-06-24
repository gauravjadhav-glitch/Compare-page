"""
ATD (Attention To Detail) bug detection.
Analyzes pages for internal design consistency + cross-page Live vs UAT differences.
"""

import re
from collections import Counter, defaultdict

from analyzer import (
    Difference,
    annotate_crop,
    humanize_element,
    get_section_name,
    _parse_px,
    _normalize_color,
)


STANDARD_TYPE_SCALE = {10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72}

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
HEADING_RANK = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

SKIP_TAGS_ATD = {"div", "section", "article", "main", "ul", "ol", "table", "form", "td", "th"}


# ── Helpers ────────────────────────────────────────────────────────

def _parse_weight(w: str) -> int:
    w = (w or "").strip().lower()
    named = {"normal": 400, "bold": 700, "lighter": 300, "bolder": 800}
    if w in named:
        return named[w]
    try:
        return int(float(w))
    except (ValueError, TypeError):
        return 400


def _classify_case(text: str) -> str:
    text = text.strip()
    if not text or len(text) < 2:
        return "unknown"
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return "unknown"
    if all(c.isupper() for c in alpha_chars):
        return "ALL CAPS"
    if text == text.title():
        return "Title Case"
    if text[0].isupper() and all(c.islower() for c in alpha_chars[1:]):
        return "Sentence case"
    if all(c.islower() for c in alpha_chars):
        return "lowercase"
    return "Mixed"


def _parse_rgb(color_str: str):
    match = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str or "")
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def _colors_similar(c1, c2, tolerance=10):
    if c1 is None or c2 is None:
        return c1 == c2
    return all(abs(a - b) <= tolerance for a, b in zip(c1, c2))


def _find_mode(values):
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _normalize_font_name(font):
    return (font or "").split(",")[0].strip().strip('"').strip("'").lower()


def _is_button_like(el):
    if el.tag == "button":
        return True
    if el.tag == "a":
        bg = (getattr(el, "background_color", "") or "").strip()
        border = (getattr(el, "border", "") or "").strip()
        if bg and bg not in ("rgba(0, 0, 0, 0)", "rgba(0,0,0,0)", "transparent", "initial", "inherit"):
            return True
        if border and "0px" not in border and "none" not in border:
            return True
    return False


def _group_elements_by_role(elements):
    groups = defaultdict(list)
    for el in elements:
        text = (el.text or "").strip()
        if not text or len(text) < 2:
            if el.tag not in HEADING_TAGS:
                continue

        if el.tag in SKIP_TAGS_ATD:
            continue

        if _is_button_like(el):
            groups["button"].append(el)
        elif el.tag in HEADING_TAGS:
            groups[el.tag].append(el)
            groups["all_headings"].append(el)
        elif el.tag == "a":
            groups["link"].append(el)
        elif el.tag == "label":
            groups["label"].append(el)
        elif el.tag == "p":
            groups["paragraph"].append(el)
        elif el.tag == "span" and len(text) > 3:
            groups["span"].append(el)
        elif el.tag in ("input", "textarea", "select"):
            groups["form_input"].append(el)
        elif el.tag == "li":
            groups["list_item"].append(el)
        elif el.tag == "nav":
            groups["nav"].append(el)
        elif el.tag == "footer":
            groups["footer"].append(el)

    return groups


def _make_diff(category, severity, prop, element, value1, value2, description, screenshot, sections, url, count=1):
    element_name = humanize_element(element.tag, element.text)
    section_name = get_section_name(element.bounding_box, sections)
    crop = annotate_crop(screenshot, element.bounding_box, color="orange", label="ATD")
    return Difference(
        category=category,
        severity=severity,
        element=element.selector,
        property=prop,
        value1=str(value1),
        value2=str(value2),
        description=f"ATD: {description}",
        human_description=description,
        section_name=section_name,
        element_name=element_name,
        navigation=f"Open {url} → {section_name} → Find {element_name}",
        crop1_bytes=crop,
        crop2_bytes=b"",
        count=count,
    )


def _make_cross_diff(category, severity, prop, uat_el, live_el, value1, value2, description,
                      uat_screenshot, live_screenshot, uat_sections, uat_url, count=1):
    element_name = humanize_element(uat_el.tag, uat_el.text)
    section_name = get_section_name(uat_el.bounding_box, uat_sections)
    crop_uat = annotate_crop(uat_screenshot, uat_el.bounding_box, color="orange", label="UAT")
    crop_live = b""
    if live_el:
        crop_live = annotate_crop(live_screenshot, live_el.bounding_box, color="green", label="LIVE")
    return Difference(
        category=category,
        severity=severity,
        element=uat_el.selector,
        property=prop,
        value1=str(value1),
        value2=str(value2),
        description=f"ATD: {description}",
        human_description=description,
        section_name=section_name,
        element_name=element_name,
        navigation=f"Open {uat_url} → {section_name} → Find {element_name}",
        crop1_bytes=crop_live,
        crop2_bytes=crop_uat,
        count=count,
    )


def _deduplicate_atd(diffs):
    seen = {}
    for d in diffs:
        key = (d.category, d.property, d.value1)
        if key not in seen:
            seen[key] = d
        else:
            seen[key].count = getattr(seen[key], "count", 1) + getattr(d, "count", 1)
    unique = list(seen.values())
    severity_rank = {"critical": 0, "major": 1, "minor": 2}
    unique.sort(key=lambda d: (severity_rank.get(d.severity, 3), -getattr(d, "count", 1)))
    return unique


# ── Check 1: Typography Hierarchy ──────────────────────────────────

def check_typography_hierarchy(elements, screenshot, sections, url):
    diffs = []
    groups = _group_elements_by_role(elements)

    heading_levels = {}
    for tag in HEADING_TAGS:
        if tag in groups:
            sizes = [_parse_px(el.font_size) for el in groups[tag]]
            weights = [_parse_weight(el.font_weight) for el in groups[tag]]
            if sizes:
                heading_levels[tag] = {
                    "median_size": sorted(sizes)[len(sizes) // 2],
                    "max_weight": max(weights),
                    "elements": groups[tag],
                }

    sorted_tags = sorted(heading_levels.keys(), key=lambda t: HEADING_RANK[t])
    for i in range(len(sorted_tags) - 1):
        higher = sorted_tags[i]
        lower = sorted_tags[i + 1]
        h_data = heading_levels[higher]
        l_data = heading_levels[lower]

        if l_data["median_size"] > h_data["median_size"]:
            el = l_data["elements"][0]
            diffs.append(_make_diff(
                "Typography Hierarchy", "major", "heading-level-inversion", el,
                f"<{lower}> is {l_data['median_size']}px",
                f"Should be <= <{higher}> at {h_data['median_size']}px",
                f"Heading inversion: <{lower}> ({l_data['median_size']}px) is LARGER than <{higher}> ({h_data['median_size']}px)",
                screenshot, sections, url,
            ))

    body_elements = []
    for tag in ("p", "span", "label", "li"):
        if tag in groups:
            body_elements.extend(groups[tag])

    hierarchy_violations = defaultdict(list)
    for h_tag, h_data in heading_levels.items():
        h_weight = h_data["max_weight"]
        h_size = h_data["median_size"]

        for body_el in body_elements:
            body_weight = _parse_weight(body_el.font_weight)
            body_size = _parse_px(body_el.font_size)
            body_y = body_el.bounding_box.get("y", 0)

            for h_el in h_data["elements"]:
                h_y = h_el.bounding_box.get("y", 0)
                if abs(body_y - h_y) > 500:
                    continue
                if body_weight > h_weight and body_size >= h_size * 0.8:
                    key = (h_tag, body_weight, h_weight)
                    hierarchy_violations[key].append(body_el)
                    break

    for (h_tag, body_w, head_w), els in hierarchy_violations.items():
        representative = els[0]
        diffs.append(_make_diff(
            "Typography Hierarchy", "critical", "hierarchy-violation", representative,
            f"Body weight: {body_w}, heading <{h_tag}> weight: {head_w}",
            f"Body text should be lighter than <{h_tag}> heading",
            f"Broken hierarchy: {len(els)} body elements (weight {body_w}) are BOLDER than <{h_tag}> heading (weight {head_w})",
            screenshot, sections, url, count=len(els),
        ))

    no_diff_found = set()
    for h_tag, h_data in heading_levels.items():
        for h_el in h_data["elements"]:
            h_size = _parse_px(h_el.font_size)
            h_weight = _parse_weight(h_el.font_weight)

            for body_el in body_elements:
                body_size = _parse_px(body_el.font_size)
                body_weight = _parse_weight(body_el.font_weight)
                if abs(body_el.bounding_box.get("y", 0) - h_el.bounding_box.get("y", 0)) > 300:
                    continue
                if h_size == body_size and h_weight == body_weight and h_size > 0:
                    if h_tag not in no_diff_found:
                        no_diff_found.add(h_tag)
                        diffs.append(_make_diff(
                            "Typography Hierarchy", "minor", "hierarchy-violation", h_el,
                            f"<{h_tag}> {h_size}px/{h_weight}",
                            "Heading should be visually distinct from body text",
                            f"No visual differentiation: <{h_tag}> has same size ({h_size}px) and weight ({h_weight}) as nearby body text",
                            screenshot, sections, url,
                        ))
                    break

    return _deduplicate_atd(diffs)


# ── Check 2: Type Scale ────────────────────────────────────────────

def check_type_scale(elements, screenshot, sections, url, allowed_sizes=None):
    scale = allowed_sizes or STANDARD_TYPE_SCALE
    diffs = []
    off_scale = defaultdict(list)

    for el in elements:
        text = (el.text or "").strip()
        if not text or el.tag in SKIP_TAGS_ATD:
            continue
        size = _parse_px(el.font_size)
        rounded = round(size)
        if rounded < 8 or rounded > 100:
            continue
        if rounded not in scale:
            off_scale[rounded].append(el)

    for size_val, els in off_scale.items():
        below = max((s for s in scale if s < size_val), default=None)
        above = min((s for s in scale if s > size_val), default=None)
        suggestion_parts = []
        if below:
            suggestion_parts.append(f"{below}px")
        if above:
            suggestion_parts.append(f"{above}px")
        suggestion = " or ".join(suggestion_parts)

        has_important = any(e.tag in HEADING_TAGS or _is_button_like(e) for e in els)
        severity = "major" if has_important else "minor"

        representative = els[0]
        tag_counts = Counter(e.tag for e in els)
        tag_summary = ", ".join(f"{count}x <{tag}>" for tag, count in tag_counts.most_common(3))

        diffs.append(_make_diff(
            "Design System", severity, "off-scale-font", representative,
            f"{size_val}px (used by {len(els)} elements: {tag_summary})",
            f"Nearest standard sizes: {suggestion}",
            f"Non-standard font size {size_val}px found on {len(els)} elements ({tag_summary}). Standard type scale uses {suggestion}",
            screenshot, sections, url, count=len(els),
        ))

    return diffs


# ── Check 3: Semantic HTML ─────────────────────────────────────────

def check_semantic_html(elements, screenshot, sections, url):
    diffs = []

    h1_elements = [el for el in elements if el.tag == "h1"]
    if len(h1_elements) > 1:
        diffs.append(_make_diff(
            "Semantic HTML", "major", "multiple-h1", h1_elements[1],
            f"{len(h1_elements)} <h1> tags found on page",
            "Page should have exactly one <h1>",
            f"Multiple <h1> tags: page has {len(h1_elements)} <h1> elements. Only one <h1> should exist per page",
            screenshot, sections, url, count=len(h1_elements) - 1,
        ))

    title_divs = []
    for el in elements:
        if el.tag in ("div", "span"):
            size = _parse_px(el.font_size)
            weight = _parse_weight(el.font_weight)
            text = (el.text or "").strip()
            y_pos = el.bounding_box.get("y", 0)
            if size >= 20 and weight >= 600 and len(text) > 3 and y_pos < 500:
                title_divs.append(el)

    if title_divs:
        diffs.append(_make_diff(
            "Semantic HTML", "major", "wrong-semantic-tag", title_divs[0],
            f"<{title_divs[0].tag}> with large/bold text used as title",
            "Should use <h1> or <h2> for page titles",
            f'{len(title_divs)} element(s) look like page titles but use <div>/<span> instead of heading tags',
            screenshot, sections, url, count=len(title_divs),
        ))

    form_inputs = [el for el in elements if el.tag in ("input", "textarea", "select")]
    label_issues = 0
    representative_label = None
    for inp in form_inputs:
        inp_y = inp.bounding_box.get("y", 0)
        inp_x = inp.bounding_box.get("x", 0)
        for el in elements:
            if el.tag in ("p", "span", "div") and (el.text or "").strip():
                el_y = el.bounding_box.get("y", 0)
                el_x = el.bounding_box.get("x", 0)
                text = el.text.strip()
                if abs(el_y - inp_y) < 60 and abs(el_x - inp_x) < 300 and len(text) < 40:
                    size = _parse_px(el.font_size)
                    if 10 <= size <= 16:
                        label_issues += 1
                        if not representative_label:
                            representative_label = el
                        break

    if representative_label and label_issues > 0:
        diffs.append(_make_diff(
            "Semantic HTML", "minor", "wrong-semantic-tag", representative_label,
            f"{label_issues} form label(s) use non-semantic tags",
            "<label> tag for accessibility",
            f'{label_issues} form label(s) use <{representative_label.tag}> instead of <label> tag',
            screenshot, sections, url, count=label_issues,
        ))

    return diffs


# ── Check 4: Element Consistency ───────────────────────────────────

def check_element_consistency(elements, screenshot, sections, url):
    diffs = []
    groups = _group_elements_by_role(elements)

    check_roles = ["button", "h1", "h2", "h3", "h4", "link", "label"]
    props_to_check = [
        ("font_size", "font-size"),
        ("font_weight", "font-weight"),
        ("font_family", "font-family"),
        ("color", "color"),
    ]

    for role in check_roles:
        els = groups.get(role, [])
        if len(els) < 3:
            continue

        is_important = role in ("button", "h1", "h2")

        for attr, prop_name in props_to_check:
            values = []
            for el in els:
                val = getattr(el, attr, "")
                if prop_name == "font-size":
                    val = str(round(_parse_px(val)))
                elif prop_name == "font-weight":
                    val = str(_parse_weight(val))
                elif prop_name == "color":
                    val = _normalize_color(val)
                elif prop_name == "font-family":
                    val = _normalize_font_name(val)
                values.append((val, el))

            if not values:
                continue

            val_counts = Counter(v for v, _ in values)
            if len(val_counts) <= 1:
                continue

            mode_val = val_counts.most_common(1)[0][0]
            outlier_groups = defaultdict(list)
            for v, el in values:
                if v != mode_val:
                    outlier_groups[v].append(el)

            if not outlier_groups:
                continue

            severity = "major" if is_important else "minor"
            role_label = role.replace("_", " ").title()

            for out_val, out_els in outlier_groups.items():
                representative = out_els[0]
                count = len(out_els)
                diffs.append(_make_diff(
                    "Element Consistency", severity, "inconsistent-style", representative,
                    f"{prop_name}: {out_val} ({count} elements)",
                    f"{prop_name}: {mode_val} (used by {val_counts[mode_val]}/{len(els)} {role_label}s)",
                    f"Inconsistent {prop_name} on {role_label}: {count} element(s) use {out_val} while {val_counts[mode_val]}/{len(els)} others use {mode_val}",
                    screenshot, sections, url, count=count,
                ))

    return _deduplicate_atd(diffs)


# ── Check 5: Text Case ────────────────────────────────────────────

def check_text_case(elements, screenshot, sections, url):
    diffs = []
    groups = _group_elements_by_role(elements)

    for role in ["button", "link"]:
        els = groups.get(role, [])
        if len(els) < 2:
            continue

        case_map = defaultdict(list)
        for el in els:
            text = (el.text or "").strip()
            if len(text) < 2:
                continue

            transform = (getattr(el, "text_transform", "") or "").lower()
            if transform == "uppercase":
                case_type = "ALL CAPS"
            elif transform == "lowercase":
                case_type = "lowercase"
            elif transform == "capitalize":
                case_type = "Title Case"
            else:
                case_type = _classify_case(text)

            if case_type == "unknown":
                continue
            case_map[case_type].append(el)

        if len(case_map) <= 1:
            continue

        total = sum(len(v) for v in case_map.values())
        dominant_case = max(case_map.keys(), key=lambda k: len(case_map[k]))
        dominant_count = len(case_map[dominant_case])

        role_label = role.title()

        for case_type, case_els in case_map.items():
            if case_type == dominant_case:
                continue
            count = len(case_els)
            representative = case_els[0]
            examples = ", ".join(f'"{(e.text or "").strip()[:20]}"' for e in case_els[:3])

            diffs.append(_make_diff(
                "Text Case", "major", "case-mismatch", representative,
                f'{case_type} ({count} elements): {examples}',
                f"{dominant_case} (used by {dominant_count}/{total} {role_label}s)",
                f'{role_label} text casing inconsistent: {count} element(s) are {case_type} (e.g. {examples}) but {dominant_count}/{total} use {dominant_case}',
                screenshot, sections, url, count=count,
            ))

    return _deduplicate_atd(diffs)


# ── Check 6: Color Consistency ─────────────────────────────────────

def check_color_consistency(elements, screenshot, sections, url):
    diffs = []
    groups = _group_elements_by_role(elements)

    check_roles = ["button", "h1", "h2", "h3", "link", "label"]

    for role in check_roles:
        els = groups.get(role, [])
        if len(els) < 2:
            continue

        is_important = role in ("button", "h1", "h2")

        color_els = []
        for el in els:
            rgb = _parse_rgb(el.color)
            if rgb:
                color_els.append((rgb, el))

        if len(color_els) < 2:
            continue

        clusters = []
        for rgb, el in color_els:
            placed = False
            for cluster in clusters:
                if _colors_similar(rgb, cluster[0][0]):
                    cluster.append((rgb, el))
                    placed = True
                    break
            if not placed:
                clusters.append([(rgb, el)])

        if len(clusters) <= 1:
            continue

        clusters.sort(key=len, reverse=True)
        dominant_cluster = clusters[0]
        dominant_rgb = dominant_cluster[0][0]
        dominant_color_str = f"rgb({dominant_rgb[0]},{dominant_rgb[1]},{dominant_rgb[2]})"

        role_label = role.replace("_", " ").title()
        severity = "major" if is_important else "minor"

        for cluster in clusters[1:]:
            rgb_val = cluster[0][0]
            actual_color = f"rgb({rgb_val[0]},{rgb_val[1]},{rgb_val[2]})"
            count = len(cluster)
            representative = cluster[0][1]

            diffs.append(_make_diff(
                "Color Consistency", severity, "color-inconsistency", representative,
                f"color: {actual_color} ({count} elements)",
                f"color: {dominant_color_str} (used by {len(dominant_cluster)}/{len(color_els)} {role_label}s)",
                f"Inconsistent color on {role_label}: {count} element(s) use {actual_color} while {len(dominant_cluster)}/{len(color_els)} others use {dominant_color_str}",
                screenshot, sections, url, count=count,
            ))

    return _deduplicate_atd(diffs)


# ── Check 7: Font Weight Consistency ───────────────────────────────

def check_font_weight_consistency(elements, screenshot, sections, url):
    diffs = []
    groups = _group_elements_by_role(elements)

    check_roles = ["button", "h1", "h2", "h3", "h4", "link", "label", "paragraph", "list_item"]

    for role in check_roles:
        els = groups.get(role, [])
        if len(els) < 3:
            continue

        size_buckets = defaultdict(list)
        for el in els:
            size = round(_parse_px(el.font_size) / 2) * 2
            weight = _parse_weight(el.font_weight)
            size_buckets[size].append((weight, el))

        for size_bucket, weight_els in size_buckets.items():
            if len(weight_els) < 3:
                continue

            weights = [w for w, _ in weight_els]
            mode_weight = _find_mode(weights)
            mode_count = weights.count(mode_weight)

            outlier_groups = defaultdict(list)
            for w, el in weight_els:
                if w != mode_weight:
                    outlier_groups[w].append(el)

            role_label = role.replace("_", " ").title()

            for w, out_els in outlier_groups.items():
                diff_amount = abs(w - mode_weight)
                severity = "major" if diff_amount >= 200 else "minor"
                count = len(out_els)
                representative = out_els[0]

                diffs.append(_make_diff(
                    "Font Weight Consistency", severity, "weight-inconsistency", representative,
                    f"font-weight: {w} ({count} elements at ~{size_bucket}px)",
                    f"font-weight: {mode_weight} (used by {mode_count}/{len(weight_els)} similar {role_label}s)",
                    f"Inconsistent font-weight on {role_label}: {count} element(s) use {w} while {mode_count}/{len(weight_els)} use {mode_weight} at ~{size_bucket}px",
                    screenshot, sections, url, count=count,
                ))

    return _deduplicate_atd(diffs)


# ── Check 8: Cross-Page Font Comparison (Live vs UAT) ──────────────

def compare_fonts_cross_page(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    diffs = []

    live_by_role = _group_elements_by_role(live_elements)
    uat_by_role = _group_elements_by_role(uat_elements)

    all_roles = set(live_by_role.keys()) | set(uat_by_role.keys())
    seen_font_pairs = set()

    for role in sorted(all_roles):
        live_els = live_by_role.get(role, [])
        uat_els = uat_by_role.get(role, [])
        if not live_els or not uat_els:
            continue

        live_fonts = Counter(_normalize_font_name(el.font_family) for el in live_els)
        uat_fonts = Counter(_normalize_font_name(el.font_family) for el in uat_els)

        live_dominant = live_fonts.most_common(1)[0][0] if live_fonts else ""
        uat_dominant = uat_fonts.most_common(1)[0][0] if uat_fonts else ""

        if live_dominant == uat_dominant or not live_dominant or not uat_dominant:
            continue

        pair_key = (role, uat_dominant, live_dominant)
        if pair_key in seen_font_pairs:
            continue
        seen_font_pairs.add(pair_key)

        is_important = role in ("button", "h1", "h2", "h3", "all_headings")
        severity = "critical" if is_important else "major"
        role_label = role.replace("_", " ").title()

        mismatched_count = sum(1 for el in uat_els if _normalize_font_name(el.font_family) != live_dominant)
        representative_uat = next((el for el in uat_els if _normalize_font_name(el.font_family) != live_dominant), uat_els[0])
        representative_live = live_els[0]

        diffs.append(_make_cross_diff(
            "Font Mismatch (Live vs UAT)", severity, "font-family-mismatch",
            representative_uat, representative_live,
            f"UAT: {uat_dominant} ({mismatched_count} {role_label} elements)",
            f"Live: {live_dominant}",
            f"Font mismatch on {role_label}: UAT uses '{uat_dominant}' but Live uses '{live_dominant}' ({mismatched_count} elements affected)",
            uat_screenshot, live_screenshot, uat_sections, uat_url, count=mismatched_count,
        ))

    live_font_map = defaultdict(list)
    uat_font_map = defaultdict(list)
    for el in live_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 3 and el.tag not in SKIP_TAGS_ATD:
            live_font_map[text[:50]].append(el)
    for el in uat_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 3 and el.tag not in SKIP_TAGS_ATD:
            uat_font_map[text[:50]].append(el)

    matched_texts = set(live_font_map.keys()) & set(uat_font_map.keys())
    text_font_pairs = defaultdict(list)

    for text in matched_texts:
        live_el = live_font_map[text][0]
        uat_el = uat_font_map[text][0]
        live_font = _normalize_font_name(live_el.font_family)
        uat_font = _normalize_font_name(uat_el.font_family)
        if live_font != uat_font:
            text_font_pairs[(uat_font, live_font)].append((uat_el, live_el, text))

    for (uat_font, live_font), matches in text_font_pairs.items():
        pair_key = ("text_match", uat_font, live_font)
        if pair_key in seen_font_pairs:
            continue
        seen_font_pairs.add(pair_key)

        representative_uat, representative_live, sample_text = matches[0]
        count = len(matches)
        examples = ", ".join(f'"{t[:20]}"' for _, _, t in matches[:3])

        is_heading = any(u.tag in HEADING_TAGS or l.tag in HEADING_TAGS for u, l, _ in matches)
        severity = "critical" if is_heading else "major"

        diffs.append(_make_cross_diff(
            "Font Mismatch (Live vs UAT)", severity, "font-family-mismatch",
            representative_uat, representative_live,
            f"UAT: {uat_font} ({count} elements: {examples})",
            f"Live: {live_font}",
            f"Font mismatch: {count} element(s) use '{uat_font}' on UAT but '{live_font}' on Live (e.g. {examples})",
            uat_screenshot, live_screenshot, uat_sections, uat_url, count=count,
        ))

    return _deduplicate_atd(diffs)


# ── Check 9: Text Formatting & Spacing (Live vs UAT) ──────────────

def compare_text_formatting(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    diffs = []

    live_texts = {}
    for el in live_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 3 and el.tag not in SKIP_TAGS_ATD:
            live_texts.setdefault(el.tag, {})[text[:80]] = el

    uat_texts = {}
    for el in uat_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 3 and el.tag not in SKIP_TAGS_ATD:
            uat_texts.setdefault(el.tag, {})[text[:80]] = el

    currency_pattern = re.compile(r'[₹$€£¥]\s*[\d,]+')
    spacing_issues = []
    truncation_issues = []

    for tag in set(live_texts.keys()) & set(uat_texts.keys()):
        for live_text, live_el in live_texts[tag].items():
            for uat_text, uat_el in uat_texts[tag].items():
                clean_live = re.sub(r'\s+', '', live_text)
                clean_uat = re.sub(r'\s+', '', uat_text)

                if clean_live == clean_uat and live_text != uat_text:
                    live_currency = currency_pattern.findall(live_text)
                    uat_currency = currency_pattern.findall(uat_text)
                    if live_currency or uat_currency:
                        spacing_issues.append((uat_el, live_el, uat_text, live_text))
                    continue

                if len(live_text) > 5 and len(uat_text) > 5:
                    if live_text[:5] == uat_text[:5] and abs(len(live_text) - len(uat_text)) > 5:
                        truncation_issues.append((uat_el, live_el, uat_text, live_text))

    if spacing_issues:
        uat_el, live_el, uat_text, live_text = spacing_issues[0]
        diffs.append(_make_cross_diff(
            "Text Formatting (Live vs UAT)", "major", "spacing-format",
            uat_el, live_el,
            f'UAT: "{uat_text[:40]}"',
            f'Live: "{live_text[:40]}"',
            f'Text spacing/formatting differs: {len(spacing_issues)} element(s) have different whitespace. E.g. UAT: "{uat_text[:30]}" vs Live: "{live_text[:30]}"',
            uat_screenshot, live_screenshot, uat_sections, uat_url, count=len(spacing_issues),
        ))

    if truncation_issues:
        uat_el, live_el, uat_text, live_text = truncation_issues[0]
        diffs.append(_make_cross_diff(
            "Text Formatting (Live vs UAT)", "major", "text-truncation",
            uat_el, live_el,
            f'UAT: "{uat_text[:40]}" ({len(uat_text)} chars)',
            f'Live: "{live_text[:40]}" ({len(live_text)} chars)',
            f'Text truncation differs: {len(truncation_issues)} element(s) have different text lengths. E.g. UAT has {len(uat_text)} chars vs Live has {len(live_text)} chars',
            uat_screenshot, live_screenshot, uat_sections, uat_url, count=len(truncation_issues),
        ))

    return diffs


# ── Check 10: Missing Navigation Elements (Live vs UAT) ───────────

def compare_navigation_elements(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    diffs = []

    nav_tags = {"a", "button", "li", "nav"}
    live_nav = set()
    live_nav_els = {}
    for el in live_elements:
        if el.tag in nav_tags:
            text = (el.text or "").strip()
            if text and 2 <= len(text) <= 60:
                key = text.lower()
                live_nav.add(key)
                live_nav_els[key] = el

    uat_nav = set()
    uat_nav_els = {}
    for el in uat_elements:
        if el.tag in nav_tags:
            text = (el.text or "").strip()
            if text and 2 <= len(text) <= 60:
                key = text.lower()
                uat_nav.add(key)
                uat_nav_els[key] = el

    missing_on_uat = live_nav - uat_nav
    extra_on_uat = uat_nav - live_nav

    if missing_on_uat:
        important_missing = [t for t in missing_on_uat if len(t) > 3]
        if important_missing:
            sample = important_missing[0]
            representative = live_nav_els[sample]
            all_items = ", ".join(f'"{t}"' for t in sorted(important_missing))
            count = len(important_missing)
            severity = "critical" if count > 3 else "major"

            section_name = get_section_name(representative.bounding_box, live_sections)
            element_name = humanize_element(representative.tag, representative.text)
            crop_live = annotate_crop(live_screenshot, representative.bounding_box, color="green", label="LIVE - EXISTS")

            diffs.append(Difference(
                category="Missing Elements (Live vs UAT)",
                severity=severity,
                element=representative.selector,
                property="missing-nav-element",
                value1=f"MISSING on UAT ({count} items): {all_items}",
                value2=f"Present on Live",
                description=f"ATD: {count} navigation/link element(s) present on Live but missing on UAT",
                human_description=f"{count} navigation element(s) present on Live but MISSING on UAT: {all_items}",
                section_name=section_name,
                element_name=element_name,
                navigation=f"Open {live_url} → {section_name} → Find {element_name}",
                crop1_bytes=crop_live,
                crop2_bytes=b"",
                count=count,
            ))

    if extra_on_uat:
        important_extra = [t for t in extra_on_uat if len(t) > 3]
        if important_extra:
            sample = important_extra[0]
            representative = uat_nav_els[sample]
            all_items = ", ".join(f'"{t}"' for t in sorted(important_extra))
            count = len(important_extra)

            section_name = get_section_name(representative.bounding_box, uat_sections)
            element_name = humanize_element(representative.tag, representative.text)
            crop_uat = annotate_crop(uat_screenshot, representative.bounding_box, color="orange", label="UAT - EXTRA")

            diffs.append(Difference(
                category="Extra Elements (Live vs UAT)",
                severity="major",
                element=representative.selector,
                property="extra-nav-element",
                value1=f"EXTRA on UAT ({count} items): {all_items}",
                value2=f"Not on Live",
                description=f"ATD: {count} element(s) on UAT but not on Live",
                human_description=f"{count} element(s) appear on UAT but NOT on Live: {all_items}",
                section_name=section_name,
                element_name=element_name,
                navigation=f"Open {uat_url} → {section_name} → Find {element_name}",
                crop1_bytes=b"",
                crop2_bytes=crop_uat,
                count=count,
            ))

    return diffs


# ── Check 11: Element Style Cross-Page (Live vs UAT) ──────────────

def compare_element_styles(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    diffs = []

    live_by_text = {}
    for el in live_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 2 and el.tag not in SKIP_TAGS_ATD:
            key = (el.tag, text[:50].lower())
            if key not in live_by_text:
                live_by_text[key] = el

    uat_by_text = {}
    for el in uat_elements:
        text = (el.text or "").strip()
        if text and len(text) >= 2 and el.tag not in SKIP_TAGS_ATD:
            key = (el.tag, text[:50].lower())
            if key not in uat_by_text:
                uat_by_text[key] = el

    matched_keys = set(live_by_text.keys()) & set(uat_by_text.keys())

    style_diffs = defaultdict(list)

    for key in matched_keys:
        live_el = live_by_text[key]
        uat_el = uat_by_text[key]
        tag, text = key

        if tag in ("li", "span", "p") and len(text) < 5:
            continue

        props = []

        live_weight = _parse_weight(live_el.font_weight)
        uat_weight = _parse_weight(uat_el.font_weight)
        if abs(live_weight - uat_weight) >= 100:
            props.append(("font-weight", str(uat_weight), str(live_weight)))

        live_size = round(_parse_px(live_el.font_size))
        uat_size = round(_parse_px(uat_el.font_size))
        if abs(live_size - uat_size) >= 2:
            props.append(("font-size", f"{uat_size}px", f"{live_size}px"))

        live_color = _normalize_color(live_el.color)
        uat_color = _normalize_color(uat_el.color)
        if live_color != uat_color:
            live_rgb = _parse_rgb(live_el.color)
            uat_rgb = _parse_rgb(uat_el.color)
            if not _colors_similar(live_rgb, uat_rgb, tolerance=15):
                props.append(("color", uat_color, live_color))

        for prop_name, uat_val, live_val in props:
            diff_key = (tag, prop_name, uat_val, live_val)
            style_diffs[diff_key].append((uat_el, live_el, text))

    for (tag, prop_name, uat_val, live_val), matches in style_diffs.items():
        count = len(matches)
        uat_el, live_el, sample_text = matches[0]
        examples = ", ".join(f'"{t[:20]}"' for _, _, t in matches[:3])

        is_important = tag in ("button", "h1", "h2", "h3", "a", "nav")
        severity = "critical" if is_important and prop_name in ("font-weight", "font-size") else "major"

        diffs.append(_make_cross_diff(
            "Style Mismatch (Live vs UAT)", severity, "style-mismatch",
            uat_el, live_el,
            f"UAT {prop_name}: {uat_val}",
            f"Live {prop_name}: {live_val}",
            f"Style mismatch on <{tag}>: {prop_name} is {uat_val} on UAT but {live_val} on Live. {count} element(s) affected (e.g. {examples})",
            uat_screenshot, live_screenshot, uat_sections, uat_url, count=count,
        ))

    return _deduplicate_atd(diffs)


# ── Check 12: Content Visibility (Live vs UAT) ────────────────────

def compare_content_visibility(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    diffs = []

    important_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "button", "label", "a", "p", "span", "li", "nav", "footer"}

    live_content = set()
    live_content_els = {}
    for el in live_elements:
        if el.tag not in important_tags:
            continue
        text = (el.text or "").strip()
        if not text or len(text) < 3 or len(text) > 100:
            continue
        key = text.lower()
        live_content.add(key)
        if key not in live_content_els:
            live_content_els[key] = el

    uat_content = set()
    uat_content_els = {}
    for el in uat_elements:
        if el.tag not in important_tags:
            continue
        text = (el.text or "").strip()
        if not text or len(text) < 3 or len(text) > 100:
            continue
        key = text.lower()
        uat_content.add(key)
        if key not in uat_content_els:
            uat_content_els[key] = el

    visible_only_on_uat = uat_content - live_content
    visible_only_on_live = live_content - uat_content

    significant_uat_only = [t for t in visible_only_on_uat if len(t) > 5 and not t.isdigit()]
    significant_live_only = [t for t in visible_only_on_live if len(t) > 5 and not t.isdigit()]

    if len(significant_uat_only) > 3:
        heading_extras = [t for t in significant_uat_only if uat_content_els[t].tag in HEADING_TAGS]
        label_extras = [t for t in significant_uat_only if uat_content_els[t].tag in ("label", "span", "p")]

        if heading_extras:
            sample = heading_extras[0]
            representative = uat_content_els[sample]
            all_items = ", ".join(f'"{t}"' for t in heading_extras)
            crop_uat = annotate_crop(uat_screenshot, representative.bounding_box, color="orange", label="UAT ONLY")

            diffs.append(Difference(
                category="Content Visibility (Live vs UAT)",
                severity="major",
                element=representative.selector,
                property="extra-content-uat",
                value1=f"Visible on UAT only ({len(heading_extras)} headings): {all_items}",
                value2="Not visible on Live",
                description=f"ATD: {len(heading_extras)} heading(s) visible on UAT but not on Live",
                human_description=f"{len(heading_extras)} heading(s) visible on UAT but NOT on Live: {all_items}",
                section_name=get_section_name(representative.bounding_box, uat_sections),
                element_name=humanize_element(representative.tag, representative.text),
                navigation=f"Open {uat_url} → Find {all_items}",
                crop1_bytes=b"",
                crop2_bytes=crop_uat,
                count=len(heading_extras),
            ))

    if len(significant_live_only) > 3:
        important_missing = [t for t in significant_live_only if live_content_els[t].tag in HEADING_TAGS or live_content_els[t].tag == "button"]

        if important_missing:
            sample = important_missing[0]
            representative = live_content_els[sample]
            all_items = ", ".join(f'"{t}"' for t in important_missing)
            crop_live = annotate_crop(live_screenshot, representative.bounding_box, color="green", label="LIVE ONLY")

            diffs.append(Difference(
                category="Content Visibility (Live vs UAT)",
                severity="critical",
                element=representative.selector,
                property="missing-content-uat",
                value1=f"Missing on UAT ({len(important_missing)} items): {all_items}",
                value2="Visible on Live",
                description=f"ATD: {len(important_missing)} content element(s) visible on Live but missing on UAT",
                human_description=f"{len(important_missing)} content element(s) visible on Live but MISSING on UAT: {all_items}",
                section_name=get_section_name(representative.bounding_box, live_sections),
                element_name=humanize_element(representative.tag, representative.text),
                navigation=f"Open {live_url} → Find {all_items}",
                crop1_bytes=crop_live,
                crop2_bytes=b"",
                count=len(important_missing),
            ))

    return diffs


# ── Orchestrator ───────────────────────────────────────────────────

def run_atd_checks(elements, screenshot, sections, url, page_label="Page", allowed_type_scale=None):
    all_diffs = []
    all_diffs.extend(check_typography_hierarchy(elements, screenshot, sections, url))
    all_diffs.extend(check_type_scale(elements, screenshot, sections, url, allowed_type_scale))
    all_diffs.extend(check_semantic_html(elements, screenshot, sections, url))
    all_diffs.extend(check_element_consistency(elements, screenshot, sections, url))
    all_diffs.extend(check_text_case(elements, screenshot, sections, url))
    all_diffs.extend(check_color_consistency(elements, screenshot, sections, url))
    all_diffs.extend(check_font_weight_consistency(elements, screenshot, sections, url))

    for d in all_diffs:
        d.human_description = f"[{page_label}] {d.human_description}"

    return all_diffs


def run_cross_page_checks(
    live_elements, uat_elements,
    live_screenshot, uat_screenshot,
    live_sections, uat_sections,
    live_url, uat_url,
):
    all_diffs = []
    all_diffs.extend(compare_fonts_cross_page(
        live_elements, uat_elements, live_screenshot, uat_screenshot,
        live_sections, uat_sections, live_url, uat_url,
    ))
    all_diffs.extend(compare_text_formatting(
        live_elements, uat_elements, live_screenshot, uat_screenshot,
        live_sections, uat_sections, live_url, uat_url,
    ))
    all_diffs.extend(compare_navigation_elements(
        live_elements, uat_elements, live_screenshot, uat_screenshot,
        live_sections, uat_sections, live_url, uat_url,
    ))
    all_diffs.extend(compare_element_styles(
        live_elements, uat_elements, live_screenshot, uat_screenshot,
        live_sections, uat_sections, live_url, uat_url,
    ))
    all_diffs.extend(compare_content_visibility(
        live_elements, uat_elements, live_screenshot, uat_screenshot,
        live_sections, uat_sections, live_url, uat_url,
    ))
    return all_diffs
