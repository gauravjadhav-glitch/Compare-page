from analyzer import Difference
from scraper import PageData, crop_region


def run_network_checks(page_data: PageData, page_label: str = "Page") -> list:
    diffs = []

    for issue in (page_data.failed_resources or []):
        error_plain = _plain_error(issue.error_text)
        if issue.resource_type == "image":
            severity = "critical"
            prop = "broken-image"
            desc = f"An image is not loading on the page — the file could not be fetched from the server"
        elif issue.resource_type == "font":
            severity = "critical"
            prop = "broken-font"
            desc = f"A custom font file failed to load — text may appear in a fallback font"
        elif issue.resource_type == "stylesheet":
            severity = "critical"
            prop = "broken-stylesheet"
            desc = f"A CSS stylesheet failed to load — page styling may be broken or missing"
        elif issue.resource_type == "script":
            severity = "major"
            prop = "broken-script"
            desc = f"A JavaScript file failed to load — some page features may not work"
        else:
            severity = "minor"
            prop = "broken-resource"
            desc = f"A resource file failed to load from the server"

        diffs.append(Difference(
            category="Broken Resources",
            severity=severity,
            element=_shorten_url(issue.url),
            property=prop,
            value1=f"{error_plain}: {_shorten_url(issue.url)}",
            value2=f"Should load successfully",
            description=desc,
            human_description=f"[{page_label}] {desc}. URL: {_shorten_url(issue.url)}",
            section_name="Network",
            element_name=f"Broken {issue.resource_type.title()}",
            navigation=f"Open browser DevTools > Network tab > filter by status 4xx/5xx to find: {_shorten_url(issue.url)}",
            crop1_bytes=b"",
            crop2_bytes=b"",
        ))

    for broken in (page_data.broken_images or []):
        already_reported = any(
            broken["src"] in d.element for d in diffs if d.property == "broken-image"
        )
        if not already_reported:
            alt_text = broken.get("alt", "") or "no alt text"
            diffs.append(Difference(
                category="Broken Resources",
                severity="critical",
                element=_shorten_url(broken["src"]),
                property="broken-image",
                value1=f"Image is broken (not displaying)",
                value2=f"Image should display correctly",
                description=f"An image on the page is broken and not displaying — the browser found the image tag but could not render it",
                human_description=f"[{page_label}] An image is broken and not displaying on the page. URL: {_shorten_url(broken['src'])}",
                section_name="Network",
                element_name=f"Broken Image ({alt_text})" if alt_text != "no alt text" else _shorten_url(broken["src"], 50),
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
        plain_err = _plain_console_error(err["text"])
        diffs.append(Difference(
            category="Console Errors",
            severity=severity,
            element="console",
            property="console-error",
            value1=plain_err[:200],
            value2="No errors expected",
            description=f"The browser reported a JavaScript error while loading the page — this may affect functionality",
            human_description=f"[{page_label}] The browser reported an error while loading the page: {plain_err[:150]}",
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


def _plain_error(error_text: str) -> str:
    mapping = {
        "net::ERR_ABORTED": "Request was cancelled or blocked",
        "net::ERR_FAILED": "Request failed",
        "net::ERR_CONNECTION_REFUSED": "Server refused the connection",
        "net::ERR_NAME_NOT_RESOLVED": "Server address not found",
        "net::ERR_TIMED_OUT": "Request timed out",
        "net::ERR_CONNECTION_RESET": "Connection was reset",
        "net::ERR_CERT_AUTHORITY_INVALID": "Invalid SSL certificate",
    }
    for code, plain in mapping.items():
        if code in error_text:
            return plain
    return error_text


def _plain_console_error(text: str) -> str:
    if "attribute" in text.lower() and "expected" in text.lower():
        return text
    return text
