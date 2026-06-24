#!/usr/bin/env python3
import argparse
import copy
import io
import sys

from playwright.sync_api import sync_playwright

from analyzer import analyze, build_summary, VisualDiffResult, ComparisonResult, compare_visual, deduplicate_diffs
from atd_analyzer import run_atd_checks, run_cross_page_checks, _deduplicate_atd
from network_analyzer import run_network_checks
from accessibility_analyzer import run_accessibility_checks
from performance_analyzer import run_performance_checks, compare_performance_cross_page
from reporter import generate_report
from scraper import (
    scrape_page,
    find_section_by_keyword,
    filter_elements_by_range,
    filter_images_by_range,
    crop_region,
    PageData,
    SectionData,
)

VIEWPORTS = {
    "desktop": {"width": 1920, "height": 1080},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}

SECTION_ORDER = ["header", "navigation", "hero", "content", "footer"]


def apply_section_filter(page_data: PageData, section: str) -> PageData:
    from PIL import Image
    img = Image.open(io.BytesIO(page_data.screenshot))
    page_height = img.height

    y_start, y_end = find_section_by_keyword(page_data.sections, section, page_height)

    filtered_elements = filter_elements_by_range(
        [copy.deepcopy(el) for el in page_data.elements], y_start, y_end
    )
    filtered_images = filter_images_by_range(
        [copy.deepcopy(im) for im in page_data.images], y_start, y_end
    )

    section_width = img.width
    section_height = int(y_end - y_start)
    cropped_screenshot = crop_region(
        page_data.screenshot, 0, y_start, section_width, section_height, padding=0
    )

    for el in filtered_elements:
        el.bounding_box = dict(el.bounding_box)
        el.bounding_box["y"] = el.bounding_box["y"] - y_start

    for im in filtered_images:
        im.bounding_box = dict(im.bounding_box)
        im.bounding_box["y"] = im.bounding_box["y"] - y_start

    adjusted_sections = []
    for sec in page_data.sections:
        if sec.y_end > y_start and sec.y_start < y_end:
            adjusted_sections.append(SectionData(
                name=sec.name,
                y_start=max(0, sec.y_start - y_start),
                y_end=min(section_height, sec.y_end - y_start),
                crop_bytes=sec.crop_bytes,
            ))

    return PageData(
        url=page_data.url,
        viewport=page_data.viewport,
        viewport_size=page_data.viewport_size,
        screenshot=cropped_screenshot,
        elements=filtered_elements,
        page_title=page_data.page_title,
        all_text_content=page_data.all_text_content,
        images=filtered_images,
        sections=adjusted_sections,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare two web pages and generate a visual bug report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare.py https://staging.example.com https://example.com
  python compare.py url1 url2 --section header
  python compare.py url1 url2 --section footer --viewports desktop,mobile
  python compare.py url1 url2 --top-issues 30

Available sections: all, header, navigation, hero, content, footer
  "all" = one report with ALL sections combined (default)
        """,
    )
    parser.add_argument("url1", help="Reference page URL (e.g., production)")
    parser.add_argument("url2", help="Compared page URL (e.g., staging)")
    parser.add_argument("--viewports", default="desktop",
                        help="Comma-separated viewports: desktop,tablet,mobile (default: desktop)")
    parser.add_argument("--output", default="./report",
                        help="Output directory for the report (default: ./report)")
    parser.add_argument("--wait", type=int, default=3,
                        help="Seconds to wait after page load (default: 3)")
    parser.add_argument("--threshold", type=int, default=30,
                        help="Pixel difference threshold 0-255 (default: 30)")
    parser.add_argument("--top-issues", type=int, default=20,
                        help="Max issues per section in report (default: 20)")
    parser.add_argument("--section", default="all",
                        help="Compare a specific section or 'all' for everything (default: all)")
    parser.add_argument("--full-report", action="store_true",
                        help="Include full-page screenshots and minor bugs (default: compact 5-6 page report)")
    parser.add_argument("--browser", default="chromium",
                        help="Browser engine: chromium, firefox, webkit, or all (default: chromium)")
    parser.add_argument("--no-scroll", action="store_true",
                        help="Disable scroll-to-load for lazy content (default: scroll enabled)")
    parser.add_argument("--accessibility", "-a", action="store_true",
                        help="Enable WCAG accessibility checks (contrast, alt text, ARIA)")
    parser.add_argument("--performance", "-p", action="store_true",
                        help="Enable performance checks (CLS, LCP, slow resources)")
    parser.add_argument("--interactions", action="store_true",
                        help="Enable hover state and dropdown detection (adds runtime)")

    args = parser.parse_args()

    for url in [args.url1, args.url2]:
        if not url.startswith(("http://", "https://")):
            print(f"Error: Invalid URL '{url}'. Must start with http:// or https://")
            sys.exit(1)

    viewport_names = [v.strip() for v in args.viewports.split(",")]
    for v in viewport_names:
        if v not in VIEWPORTS:
            print(f"Error: Unknown viewport '{v}'. Choose from: {', '.join(VIEWPORTS.keys())}")
            sys.exit(1)

    BROWSERS = {
        "chromium": lambda p: p.chromium.launch(headless=True),
        "firefox": lambda p: p.firefox.launch(headless=True),
        "webkit": lambda p: p.webkit.launch(headless=True),
    }
    if args.browser == "all":
        browser_names = list(BROWSERS.keys())
    else:
        browser_names = [b.strip() for b in args.browser.split(",")]
    for b in browser_names:
        if b not in BROWSERS:
            print(f"Error: Unknown browser '{b}'. Choose from: {', '.join(BROWSERS.keys())}")
            sys.exit(1)

    section = args.section.lower().strip()
    if section == "all":
        sections_to_compare = SECTION_ORDER
    else:
        sections_to_compare = [section]

    enable_scroll = not args.no_scroll
    multi_browser = len(browser_names) > 1

    print(f"Comparing:")
    print(f"  Reference Page: {args.url1}")
    print(f"  Compared Page:  {args.url2}")
    print(f"  Browsers: {', '.join(browser_names)}")
    print(f"  Viewports: {', '.join(viewport_names)}")
    print(f"  Sections: {', '.join(s.upper() for s in sections_to_compare)}")
    features = []
    if enable_scroll:
        features.append("scroll")
    if args.accessibility:
        features.append("accessibility")
    if args.performance:
        features.append("performance")
    if args.interactions:
        features.append("interactions")
    features.append("network-checks")
    print(f"  Features: {', '.join(features)}")
    print()

    all_results = []
    all_atd_diffs = []

    with sync_playwright() as p:
        for browser_name in browser_names:
            browser_label = browser_name.title() if multi_browser else ""
            print(f"{'=' * 40}")
            if multi_browser:
                print(f"  Browser: {browser_name.upper()}")
                print(f"{'=' * 40}")

            browser = BROWSERS[browser_name](p)

            for vp_name in viewport_names:
                vp_size = VIEWPORTS[vp_name]
                vp_label = f"{vp_name} ({browser_name})" if multi_browser else vp_name

                print(f"[{vp_label}] Capturing reference page...")
                data1_full = scrape_page(browser, args.url1, vp_name, vp_size, args.wait,
                                         enable_scroll=enable_scroll,
                                         collect_performance=args.performance)
                print(f"[{vp_label}] Capturing compared page...")
                data2_full = scrape_page(browser, args.url2, vp_name, vp_size, args.wait,
                                         enable_scroll=enable_scroll,
                                         collect_performance=args.performance)

                print(f"[{vp_label}] Running ATD consistency checks on reference page...")
                atd_diffs_page1 = run_atd_checks(
                    data1_full.elements, data1_full.screenshot,
                    data1_full.sections, args.url1, page_label="Reference Page"
                )
                print(f"[{vp_label}] Running ATD consistency checks on compared page...")
                atd_diffs_page2 = run_atd_checks(
                    data2_full.elements, data2_full.screenshot,
                    data2_full.sections, args.url2, page_label="Compared Page"
                )

                print(f"[{vp_label}] Running network checks...")
                network_diffs_1 = run_network_checks(data1_full, page_label="Reference Page")
                network_diffs_2 = run_network_checks(data2_full, page_label="Compared Page")

                extra_diffs = network_diffs_1 + network_diffs_2

                if args.accessibility:
                    print(f"[{vp_label}] Running accessibility checks...")
                    a11y_diffs_1 = run_accessibility_checks(data1_full, page_label="Reference Page")
                    a11y_diffs_2 = run_accessibility_checks(data2_full, page_label="Compared Page")
                    extra_diffs.extend(a11y_diffs_1 + a11y_diffs_2)

                if args.performance:
                    print(f"[{vp_label}] Running performance checks...")
                    perf_diffs_1 = run_performance_checks(data1_full, page_label="Reference Page")
                    perf_diffs_2 = run_performance_checks(data2_full, page_label="Compared Page")
                    perf_cross = compare_performance_cross_page(data1_full, data2_full)
                    extra_diffs.extend(perf_diffs_1 + perf_diffs_2 + perf_cross)

                viewport_diffs = []
                for sec_name in sections_to_compare:
                    print(f"[{vp_label}] Analyzing {sec_name.upper()} section...")
                    data1 = apply_section_filter(data1_full, sec_name)
                    data2 = apply_section_filter(data2_full, sec_name)

                    result = analyze(data1, data2, args.threshold, args.top_issues)
                    viewport_diffs.extend(result.differences)

                    total_diffs = len(result.differences)
                    print(f"  [{sec_name.upper()}] Bugs: {total_diffs} | "
                          f"Pixel diff: {result.visual_diff.diff_percentage}%")

                viewport_diffs = deduplicate_diffs(viewport_diffs)

                print(f"[{vp_label}] Computing full-page visual diff...")
                full_visual = compare_visual(data1_full.screenshot, data2_full.screenshot, args.threshold)

                display_vp = vp_name.title()
                if multi_browser:
                    display_vp = f"{vp_name.title()} ({browser_name.title()})"

                merged = ComparisonResult(
                    viewport=display_vp,
                    differences=viewport_diffs,
                    visual_diff=full_visual,
                    match_percentage=full_visual.match_percentage,
                    summary=build_summary(viewport_diffs),
                )
                all_results.append(merged)
                print(f"  [{vp_label.upper()}] Combined: {full_visual.match_percentage:.1f}% match | "
                      f"{len(viewport_diffs)} bugs")

                print(f"[{vp_label}] Running cross-page checks: Live vs UAT...")
                cross_page_diffs = run_cross_page_checks(
                    data1_full.elements, data2_full.elements,
                    data1_full.screenshot, data2_full.screenshot,
                    data1_full.sections, data2_full.sections,
                    args.url1, args.url2,
                )

                atd_combined = atd_diffs_page1 + atd_diffs_page2 + cross_page_diffs + extra_diffs
                all_atd_diffs.extend(atd_combined)
                crit = sum(1 for d in atd_combined if d.severity == "critical")
                maj = sum(1 for d in atd_combined if d.severity == "major")
                minor = sum(1 for d in atd_combined if d.severity == "minor")
                print(f"  [ATD] {len(atd_combined)} issues | {crit}C {maj}M {minor}m")
                print()

            browser.close()

    all_atd_diffs = _deduplicate_atd(all_atd_diffs)
    if all_atd_diffs:
        dummy_visual = VisualDiffResult(
            diff_image=b"",
            diff_percentage=0.0,
            match_percentage=100.0,
            highlighted_image1=b"",
            highlighted_image2=b"",
        )
        atd_result = ComparisonResult(
            viewport="ATD Consistency",
            differences=all_atd_diffs,
            visual_diff=dummy_visual,
            match_percentage=max(0, 100 - len(all_atd_diffs) * 0.5),
            summary=build_summary(all_atd_diffs),
        )
        all_results.append(atd_result)

    print("Generating visual bug report...")
    report_label = "All Sections" if section == "all" else section.upper()
    compact = not args.full_report
    report_path = generate_report(args.url1, args.url2, all_results, args.output, report_label, compact=compact)
    print(f"\nReport saved: {report_path}")
    print()
    print("=" * 60)
    print("  DESIGN QA SUMMARY")
    print("=" * 60)
    for r in all_results:
        crit = sum(1 for d in r.differences if d.severity == "critical")
        maj = sum(1 for d in r.differences if d.severity == "major")
        minor = sum(1 for d in r.differences if d.severity == "minor")
        status = "PASS" if r.match_percentage >= 90 else "NEEDS REVIEW" if r.match_percentage >= 70 else "FAIL"
        print(f"  {r.viewport:30s} | {r.match_percentage:5.1f}% match | {status:12s} | {crit}C {maj}M {minor}m")
    print("=" * 60)


if __name__ == "__main__":
    main()
