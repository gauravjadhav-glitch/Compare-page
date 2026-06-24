from analyzer import Difference
from scraper import PageData


def run_performance_checks(page_data: PageData, page_label: str = "Page") -> list:
    diffs = []
    metrics = page_data.performance_metrics or {}

    cls_score = metrics.get("cls_score", 0)
    if cls_score > 0.1:
        if cls_score > 0.25:
            severity = "critical"
            desc = f"Page has excessive layout shifting (CLS: {cls_score:.3f}). Elements are moving around as the page loads, causing a very poor user experience."
        else:
            severity = "major"
            desc = f"Page has noticeable layout shifting (CLS: {cls_score:.3f}). Some elements move around during loading."

        diffs.append(Difference(
            category="Performance (Layout Shift)",
            severity=severity,
            element="page",
            property="high-cls",
            value1=f"CLS: {cls_score:.3f}",
            value2="Good: < 0.1, Needs improvement: < 0.25",
            description=desc,
            human_description=f"[{page_label}] {desc}",
            section_name="Full Page",
            element_name="Cumulative Layout Shift",
            navigation="Reload the page and watch for content that jumps or shifts position",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    lcp_ms = metrics.get("lcp_ms", 0)
    if lcp_ms > 2500:
        lcp_sec = lcp_ms / 1000
        lcp_element = metrics.get("lcp_element", "unknown")
        if lcp_ms > 4000:
            severity = "critical"
            desc = f"The main content takes {lcp_sec:.1f}s to appear (LCP). This is very slow and users may leave before the page loads."
        else:
            severity = "major"
            desc = f"The main content takes {lcp_sec:.1f}s to appear (LCP). This is slower than recommended."

        diffs.append(Difference(
            category="Performance (Loading Speed)",
            severity=severity,
            element=lcp_element,
            property="high-lcp",
            value1=f"LCP: {lcp_sec:.1f}s",
            value2="Good: < 2.5s, Needs improvement: < 4.0s",
            description=desc,
            human_description=f"[{page_label}] {desc} Largest element: {lcp_element}",
            section_name="Full Page",
            element_name=f"Largest Contentful Paint ({lcp_element})",
            navigation="Open DevTools > Lighthouse to measure loading performance",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    slow_resources = metrics.get("slow_resources", [])
    for res in slow_resources[:5]:
        duration_sec = res["duration"] / 1000
        size_kb = res.get("size", 0) / 1024

        if duration_sec > 3:
            severity = "major"
        else:
            severity = "minor"

        url_short = res["url"]
        if len(url_short) > 80:
            url_short = url_short[:77] + "..."

        desc = f"Resource took {duration_sec:.1f}s to load"
        if size_kb > 0:
            desc += f" ({size_kb:.0f} KB)"

        diffs.append(Difference(
            category="Performance (Slow Resources)",
            severity=severity,
            element=url_short,
            property="slow-resource",
            value1=f"{duration_sec:.1f}s load time",
            value2=url_short,
            description=f"{desc}: {url_short}",
            human_description=f"[{page_label}] {desc}. This slows down the page: {url_short}",
            section_name="Network",
            element_name=url_short[:50],
            navigation="Open DevTools > Network tab, sort by Time to find slow resources",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    return diffs


def compare_performance_cross_page(live_data: PageData, uat_data: PageData) -> list:
    diffs = []
    live_metrics = live_data.performance_metrics or {}
    uat_metrics = uat_data.performance_metrics or {}

    live_cls = live_metrics.get("cls_score", 0)
    uat_cls = uat_metrics.get("cls_score", 0)
    if uat_cls > live_cls + 0.1 and uat_cls > 0.1:
        diffs.append(Difference(
            category="Performance Regression",
            severity="major",
            element="page",
            property="performance-regression",
            value1=f"UAT CLS: {uat_cls:.3f}",
            value2=f"Live CLS: {live_cls:.3f}",
            description=f"UAT has more layout shifting than Live",
            human_description=f"UAT page has worse layout stability (CLS {uat_cls:.3f}) compared to Live (CLS {live_cls:.3f}). Recent changes may have introduced layout shift.",
            section_name="Full Page",
            element_name="CLS Regression",
            navigation="Compare page loading behavior between Live and UAT",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    live_lcp = live_metrics.get("lcp_ms", 0)
    uat_lcp = uat_metrics.get("lcp_ms", 0)
    if uat_lcp > live_lcp + 1000 and uat_lcp > 2500:
        diffs.append(Difference(
            category="Performance Regression",
            severity="major",
            element="page",
            property="performance-regression",
            value1=f"UAT LCP: {uat_lcp / 1000:.1f}s",
            value2=f"Live LCP: {live_lcp / 1000:.1f}s",
            description=f"UAT loads main content slower than Live",
            human_description=f"UAT takes {uat_lcp / 1000:.1f}s to show main content, compared to {live_lcp / 1000:.1f}s on Live. The page has gotten slower.",
            section_name="Full Page",
            element_name="LCP Regression",
            navigation="Load both Live and UAT side by side and compare loading speed",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    return diffs
