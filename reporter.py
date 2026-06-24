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


VERIFICATION_STEPS = {
    "inconsistent-style": "How to verify: 1) Right-click on the flagged element → Inspect. 2) In DevTools Computed tab, check the flagged property (font-size, font-weight, or color). 3) Now right-click on another element of the same type (e.g., another button) → Inspect → compare the same property. 4) All elements of the same type should have identical values.",
    "font-family-mismatch": "How to verify: 1) Open both Live and UAT pages side by side. 2) Right-click the flagged element on UAT → Inspect → Computed tab → check font-family. 3) Do the same on Live. 4) The font names should match. If UAT shows a different font, the CSS or font file needs updating.",
    "font-size": "How to verify: 1) Right-click the flagged element → Inspect → Computed tab → check font-size. 2) Compare with the same element on the reference page. 3) Both should show the same pixel value.",
    "font-weight": "How to verify: 1) Right-click the flagged element → Inspect → Computed tab → check font-weight. 2) Compare with the reference page. 3) Values like 400 = normal, 700 = bold.",
    "color": "How to verify: 1) Right-click the flagged element → Inspect → Computed tab → check color. 2) Compare the RGB value with the reference page.",
    "font-family": "How to verify: 1) Right-click the flagged element → Inspect → Computed tab → check font-family. 2) Compare with the reference page. The font name should match exactly.",
    "heading-level-inversion": "How to verify: 1) Right-click on the larger heading → Inspect → check its tag (h1, h2, h3). 2) Right-click the smaller heading → Inspect → check its tag. 3) Higher-level headings (h1) should always be bigger than lower-level (h2, h3). If h3 is bigger than h2, that's the bug.",
    "heading-body-weight": "How to verify: 1) Right-click a heading → Inspect → Computed tab → check font-weight and font-size. 2) Right-click the body text below it → check the same properties. 3) Headings should be bolder (higher font-weight) and larger than body text.",
    "hierarchy-violation": "How to verify: 1) Visually scan the page — headings should look bigger and bolder than the text below them. 2) If body text looks the same size or bolder than a heading, that's the bug. 3) Right-click both → Inspect → compare font-size and font-weight in Computed tab.",
    "off-scale-font": "How to verify: 1) Right-click the element → Inspect → Computed tab → check font-size. 2) The value should be one of the standard sizes: 12, 14, 16, 18, 20, 24, 28, 32px. 3) Odd sizes like 15px or 17px indicate the design system scale is not being followed.",
    "case-mismatch": "How to verify: 1) Look at all buttons or links of the same type on the page. 2) Check if they all use the same text style — ALL CAPS, Title Case, or lowercase. 3) If most use Title Case but one uses lowercase (or vice versa), that's the inconsistency.",
    "color-inconsistency": "How to verify: 1) Look at all elements of the same type (e.g., all buttons). 2) They should all be the same color. 3) Right-click each → Inspect → Computed tab → check color. 4) If one button is a different shade, that's the bug.",
    "weight-inconsistency": "How to verify: 1) Right-click each element of the same type → Inspect → Computed tab → check font-weight. 2) All should show the same weight value (e.g., all 400 or all 700). 3) If one element has a different weight, that's the inconsistency.",
    "wrong-semantic-tag": "How to verify: 1) Right-click the element → Inspect. 2) Check the HTML tag in the Elements panel. 3) The page title should be <h1>, form labels should be <label>, etc. 4) If a <div> or <span> is styled like a heading, it should be changed to the correct heading tag.",
    "multiple-h1": "How to verify: 1) Open DevTools Console tab. 2) Type: document.querySelectorAll('h1').length and press Enter. 3) If it shows more than 1, the page has multiple h1 tags. Only one h1 is allowed per page.",
    "missing-element": "How to verify: 1) Open both Live and UAT pages side by side. 2) Look for the flagged element on the Live page. 3) Check if it exists on UAT. 4) If it's missing on UAT, it needs to be added back.",
    "extra-element": "How to verify: 1) Open both Live and UAT pages side by side. 2) Find the flagged element on UAT. 3) Check if it exists on Live. 4) If it only appears on UAT, verify with the design team whether it should be there.",
    "missing-nav-element": "How to verify: 1) Open the Live page → look at the navigation/footer links. 2) Open the UAT page → compare the same area. 3) Note which links are present on Live but missing on UAT. 4) These need to be restored on UAT.",
    "extra-nav-element": "How to verify: 1) Open the UAT page → look at the navigation/footer links. 2) Open the Live page → compare the same area. 3) Note which links appear on UAT but not on Live. 4) Verify with the team if these new links are intentional.",
    "style-mismatch": "How to verify: 1) Open both Live and UAT pages. 2) Right-click the same element on both → Inspect → Computed tab. 3) Compare font-size, font-weight, and color values. 4) UAT should match Live exactly.",
    "spacing-format": "How to verify: 1) Open both Live and UAT pages side by side. 2) Find the flagged text and compare character-by-character. 3) Look for missing/extra spaces, different number formats, or different currency symbol spacing.",
    "text-truncation": "How to verify: 1) Open both Live and UAT pages. 2) Find the flagged text on both pages. 3) Compare the text length — if UAT shows fewer characters or adds '...' where Live doesn't, that's the truncation bug.",
    "extra-content-uat": "How to verify: 1) Open the UAT page and find the flagged content. 2) Open the Live page and check if the same content exists. 3) If it only shows on UAT, confirm with the design/product team whether it should be visible.",
    "missing-content-uat": "How to verify: 1) Open the Live page and find the flagged content. 2) Open the UAT page and check the same location. 3) If the content is missing on UAT, it needs to be restored.",
    "broken-image": "How to verify: 1) Open the page in Chrome. 2) Look for broken image icons (small square with a torn corner). 3) Or open DevTools → Network tab → filter by 'Img' → look for red 404 entries. 4) The image URL needs to be fixed or the image file needs to be uploaded.",
    "broken-font": "How to verify: 1) Open DevTools → Network tab → filter by 'Font'. 2) Look for any red/failed requests. 3) If a font file returns 404, the text will fall back to a default system font, looking different from the design.",
    "broken-stylesheet": "How to verify: 1) Open DevTools → Network tab → filter by 'CSS'. 2) Look for red/failed requests. 3) A missing stylesheet can cause the entire page to look unstyled or broken.",
    "console-error": "How to verify: 1) Open DevTools → Console tab. 2) Look for red error messages. 3) These JavaScript errors can cause buttons not to work, content not to load, or other functional bugs.",
    "contrast-fail-aa": "How to verify: 1) Look at the flagged text — is it hard to read against its background? 2) Open DevTools → Inspect the element → in Styles panel, hover over the color value → Chrome shows the contrast ratio. 3) It should be at least 4.5:1 for normal text, 3:1 for large text.",
    "missing-alt-text": "How to verify: 1) Right-click the image → Inspect. 2) Check if the <img> tag has an alt='...' attribute. 3) If alt is empty or missing, screen reader users won't know what the image shows.",
    "missing-aria-label": "How to verify: 1) Right-click the element → Inspect. 2) Check if it has aria-label='...' in the HTML. 3) If a button/link has no visible text and no aria-label, it's not accessible.",
    "tab-order-issue": "How to verify: 1) Click somewhere on the page, then press Tab repeatedly. 2) Watch which elements get focused (shown by a blue outline). 3) The focus should move in a logical order (left to right, top to bottom). 4) If focus jumps randomly, the tabindex values need fixing.",
    "high-cls": "How to verify: 1) Open the page in Chrome with DevTools open. 2) Go to Network tab → set throttling to 'Slow 3G'. 3) Reload the page and watch for content that jumps or shifts position during loading. 4) Common causes: images without width/height, late-loading banners, font swaps.",
    "high-lcp": "How to verify: 1) Open DevTools → Lighthouse tab → run a Performance audit. 2) Check the LCP (Largest Contentful Paint) value. 3) Under 2.5s is good, 2.5-4s needs improvement, over 4s is poor. 4) The main hero image or heading text is usually the LCP element.",
    "slow-resource": "How to verify: 1) Open DevTools → Network tab → sort by Time column (descending). 2) Find the flagged resource — it takes over 1 second to load. 3) Check if the file can be compressed, cached, or loaded from a CDN.",
    "performance-regression": "How to verify: 1) Open both Live and UAT pages. 2) Open DevTools → Performance tab → record a page load on each. 3) Compare the timelines. 4) If UAT is noticeably slower, recent code changes may have introduced the regression.",
    "hover-state-missing": "How to verify: 1) Move your mouse over the flagged button or link. 2) Watch if the appearance changes (color, underline, shadow, etc.). 3) If nothing happens visually, the hover state is missing. 4) Interactive elements should always give visual feedback on hover.",
    "hover-state-mismatch": "How to verify: 1) Open both Live and UAT pages. 2) Hover over the same button/link on both. 3) Compare the hover effect — color change, underline, shadow, etc. 4) UAT should match Live's hover behavior.",
    "aspect-ratio": "How to verify: 1) Look at the flagged image — does it appear stretched or squished? 2) Compare with the same image on the reference page. 3) Right-click → Inspect → check width and height values. 4) The ratio of width to height should match the original image.",
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
                "verification": VERIFICATION_STEPS.get(d.property, ""),
                "count": getattr(d, "count", 1),
                "device": getattr(d, "viewport", "") or "All",
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
