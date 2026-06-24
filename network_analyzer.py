from analyzer import Difference
from scraper import PageData, crop_region


def run_network_checks(page_data: PageData, page_label: str = "Page") -> list:
    diffs = []

    for issue in (page_data.failed_resources or []):
        if issue.resource_type == "image":
            severity = "critical"
            prop = "broken-image"
            desc = f"Image failed to load ({issue.error_text}): {_shorten_url(issue.url)}"
        elif issue.resource_type == "font":
            severity = "critical"
            prop = "broken-font"
            desc = f"Font failed to load ({issue.error_text}): {_shorten_url(issue.url)}"
        elif issue.resource_type == "stylesheet":
            severity = "critical"
            prop = "broken-stylesheet"
            desc = f"Stylesheet failed to load ({issue.error_text}): {_shorten_url(issue.url)}"
        elif issue.resource_type == "script":
            severity = "major"
            prop = "broken-script"
            desc = f"Script failed to load ({issue.error_text}): {_shorten_url(issue.url)}"
        else:
            severity = "minor"
            prop = "broken-resource"
            desc = f"Resource failed to load ({issue.error_text}): {_shorten_url(issue.url)}"

        diffs.append(Difference(
            category="Broken Resources",
            severity=severity,
            element=_shorten_url(issue.url),
            property=prop,
            value1=issue.error_text,
            value2=_shorten_url(issue.url),
            description=desc,
            human_description=f"[{page_label}] {desc}",
            section_name="Network",
            element_name=_shorten_url(issue.url, 50),
            navigation=f"Open browser DevTools > Network tab > filter by status 4xx/5xx to find: {_shorten_url(issue.url)}",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    for broken in (page_data.broken_images or []):
        already_reported = any(
            broken["src"] in d.element for d in diffs if d.property == "broken-image"
        )
        if not already_reported:
            diffs.append(Difference(
                category="Broken Resources",
                severity="critical",
                element=_shorten_url(broken["src"]),
                property="broken-image",
                value1="Image not loaded",
                value2=_shorten_url(broken["src"]),
                description=f"Image element exists but failed to render: {_shorten_url(broken['src'])}",
                human_description=f"[{page_label}] Image is broken and not displaying: {_shorten_url(broken['src'])}",
                section_name="Network",
                element_name=broken.get("alt", "") or _shorten_url(broken["src"], 50),
                navigation=f"Look for a broken image icon on the page. Image alt text: '{broken.get('alt', '')}'",
                crop1_bytes=b"",
                crop2_bytes=b"",
            ))

    error_count = 0
    for err in (page_data.console_errors or []):
        if error_count >= 5:
            break
        if err["type"] == "error":
            severity = "major"
        else:
            severity = "minor"
        diffs.append(Difference(
            category="Console Errors",
            severity=severity,
            element="console",
            property="console-error",
            value1=err["text"][:200],
            value2="",
            description=f"Browser console {err['type']}: {err['text'][:200]}",
            human_description=f"[{page_label}] JavaScript {err['type']} in browser console: {err['text'][:150]}",
            section_name="Browser Console",
            element_name=f"Console {err['type'].title()}",
            navigation="Open browser DevTools > Console tab to see this error",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))
        error_count += 1

    return diffs


def _shorten_url(url: str, max_len: int = 80) -> str:
    if len(url) <= max_len:
        return url
    return url[:max_len - 3] + "..."
