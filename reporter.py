import base64
import os
from datetime import datetime

from jinja2 import Template


def image_to_data_uri(image_bytes: bytes) -> str:
    if not image_bytes:
        return ""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = "image/jpeg" if image_bytes[:2] == b'\xff\xd8' else "image/png"
    return f"data:{mime};base64,{b64}"


SUGGESTED_FIXES = {
    "font-family": "Update the font family on the compared page to match the reference page.",
    "font-size": "Adjust the text size on the compared page to match the reference page exactly.",
    "font-weight": "Make the text boldness match between both pages.",
    "font-style": "Ensure the text style (italic/normal) matches between pages.",
    "line-height": "Adjust the line spacing to match the reference page.",
    "letter-spacing": "Correct the letter spacing to match the reference page.",
    "text-align": "Fix the text alignment (left/center/right) to match the reference.",
    "color": "Update the text color to match the reference page.",
    "margin": "Adjust the outer spacing around this element to match the reference page.",
    "padding": "Adjust the inner spacing of this element to match the reference page.",
    "display": "This element's layout type has changed — verify it displays correctly on both pages.",
    "position": "Reposition this element to match its location on the reference page.",
    "dimensions": "Resize this element to match its original dimensions on the reference page.",
    "missing-element": "This content is missing on the compared page — add it back to match the reference.",
    "extra-element": "This content only appears on the compared page — verify if it should be there.",
    "text-content": "Update the text content to match the reference page.",
    "page-title": "Update the browser tab title to match the reference page.",
    "missing-image": "The image is missing on the compared page — restore it to match the reference.",
    "extra-image": "An extra image appears on the compared page — verify if it belongs there.",
    "aspect-ratio": "Fix the image proportions so it doesn't look stretched or squished.",
    "hierarchy-violation": "Fix typography hierarchy: headings should be larger/bolder than body text, and h1 > h2 > h3 in size.",
    "heading-level-inversion": "Fix heading sizes: higher-level headings (h1) should be larger than lower-level (h2, h3).",
    "heading-body-weight": "Headings should have equal or greater font-weight than body text beneath them.",
    "off-scale-font": "Replace this font size with the nearest value from the design system type scale (12, 14, 16, 18, 20, 24, 32px).",
    "wrong-semantic-tag": "Use the correct semantic HTML tag (e.g., <h1> for page titles, <label> for form labels).",
    "multiple-h1": "A page should have exactly one <h1> tag. Demote extra headings to <h2> or lower.",
    "inconsistent-style": "Standardize styling for all elements of the same type — use consistent font, size, weight, and color.",
    "case-mismatch": "Standardize text casing: pick ALL CAPS, Title Case, or Sentence case and apply consistently across similar elements.",
    "color-inconsistency": "Use a single, consistent color value for all elements with the same semantic role.",
    "weight-inconsistency": "Use consistent font-weight values for elements of the same type and size.",
    "font-family-mismatch": "Update the UAT font-family to match the Live site. Ensure font files are loaded and CSS references the correct family name.",
    "spacing-format": "Fix text spacing/formatting to match the Live site (e.g., add space after currency symbol: '₹ 6,872' not '₹6,872').",
    "text-truncation": "Fix text truncation — ensure the same content length is displayed as on the Live site.",
    "missing-nav-element": "Restore the missing navigation/link element(s) that are present on the Live site.",
    "extra-nav-element": "Verify whether these extra navigation elements should appear — they are not on the Live site.",
    "style-mismatch": "Update the element's style (font-weight, font-size, or color) to match the Live site.",
    "extra-content-uat": "Verify if this content should be visible — it appears on UAT but not on the Live site.",
    "missing-content-uat": "Restore this content — it is visible on the Live site but missing on UAT.",
    "broken-image": "Fix the broken image: check the URL path and ensure the file exists on the server.",
    "broken-font": "Fix the broken font: ensure the font file is deployed and the @font-face CSS URL is correct.",
    "broken-stylesheet": "Fix the broken stylesheet: ensure the CSS file URL is correct and the file is deployed.",
    "broken-script": "Fix the broken script: ensure the JavaScript file URL is correct and deployed.",
    "broken-resource": "Fix this broken resource: verify the URL is correct and the file exists on the server.",
    "console-error": "Investigate the JavaScript console error and fix the underlying code issue.",
    "contrast-fail-aa": "Increase the color contrast ratio to meet WCAG AA (4.5:1 for text, 3:1 for large text).",
    "contrast-fail-aaa": "Increase the color contrast ratio to meet WCAG AAA (7:1 for text, 4.5:1 for large text).",
    "missing-alt-text": "Add descriptive alt text to this image so screen readers can describe it to users.",
    "missing-aria-label": "Add an aria-label or visible text label to this interactive element.",
    "tab-order-issue": "Review the tab order: remove positive tabindex values and ensure logical DOM order.",
    "high-cls": "Reduce layout shift by setting explicit width/height on images and avoiding dynamic content insertion above the fold.",
    "high-lcp": "Improve loading speed by optimizing the hero image/text, using compression, or preloading key assets.",
    "slow-resource": "Optimize this slow-loading resource: consider compression, CDN, or lazy loading.",
    "performance-regression": "UAT performance has regressed compared to Live — investigate recent changes.",
    "hover-state-missing": "Add a hover state (CSS :hover) to this interactive element for better user feedback.",
    "hover-state-mismatch": "Update the hover state styling to match the reference page.",
    "dropdown-missing": "The dropdown menu present on the reference page is missing — restore it.",
}


def generate_report(url1: str, url2: str, results: list, output_dir: str, section: str = "all", compact: bool = True) -> str:
    os.makedirs(output_dir, exist_ok=True)

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_template.html")
    with open(template_path, "r") as f:
        template = Template(f.read())

    total_bugs = 0
    total_critical = 0
    total_major = 0
    total_minor = 0
    all_summary = {}

    template_results = []
    for r in results:
        if "ATD" not in r.viewport:
            continue
        filtered = r.differences

        seen_keys = set()
        deduped = []
        for d in filtered:
            key = (d.category, d.property, d.value1[:40] if d.value1 else "")
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(d)
        filtered = deduped

        diffs_with_uris = []
        for d in filtered:
            diffs_with_uris.append({
                "severity": d.severity,
                "category": d.category,
                "human_description": d.human_description,
                "section_name": d.section_name,
                "element_name": d.element_name,
                "navigation": d.navigation,
                "value1": d.value1,
                "value2": d.value2,
                "crop1_uri": image_to_data_uri(d.crop1_bytes),
                "crop2_uri": image_to_data_uri(d.crop2_bytes),
                "suggested_fix": SUGGESTED_FIXES.get(d.property, "Review this element and ensure it matches the reference page."),
                "count": getattr(d, "count", 1),
            })

            total_bugs += 1
            if d.severity == "critical":
                total_critical += 1
            elif d.severity == "major":
                total_major += 1
            else:
                total_minor += 1

        for cat, counts in r.summary.items():
            if cat not in all_summary:
                all_summary[cat] = {"critical": 0, "major": 0, "minor": 0, "total": 0}
            for key in ("critical", "major", "minor", "total"):
                all_summary[cat][key] += counts.get(key, 0)

        template_results.append({
            "viewport": r.viewport,
            "match_percentage": r.match_percentage,
            "summary": r.summary,
            "visual_diff": r.visual_diff,
            "differences": diffs_with_uris,
            "highlighted_image1_uri": image_to_data_uri(r.visual_diff.highlighted_image1),
            "highlighted_image2_uri": image_to_data_uri(r.visual_diff.highlighted_image2),
            "diff_image_uri": image_to_data_uri(r.visual_diff.diff_image),
            "compact": compact,
        })

    section_label = "Full Page" if section == "all" else section.upper() + " Section"

    html = template.render(
        url1=url1,
        url2=url2,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        results=template_results,
        total_bugs=total_bugs,
        total_critical=total_critical,
        total_major=total_major,
        total_minor=total_minor,
        all_summary=all_summary,
        section_label=section_label,
    )

    report_path = os.path.join(output_dir, "comparison_report.html")
    with open(report_path, "w") as f:
        f.write(html)

    return os.path.abspath(report_path)
