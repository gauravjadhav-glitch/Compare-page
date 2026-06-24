import dataclasses
import io
from typing import Optional
from PIL import Image
from playwright.sync_api import Browser, Page


@dataclasses.dataclass
class NetworkIssue:
    url: str
    resource_type: str
    status_code: int
    error_text: str


@dataclasses.dataclass
class ElementData:
    tag: str
    selector: str
    text: str
    bounding_box: dict
    font_family: str
    font_size: str
    font_weight: str
    font_style: str
    line_height: str
    letter_spacing: str
    text_align: str
    color: str
    margin: str
    padding: str
    position: str
    display: str
    text_transform: str
    background_color: str
    border: str
    text_decoration: str
    aria_label: str = ""
    aria_role: str = ""
    tab_index: str = ""


@dataclasses.dataclass
class ImageData:
    src: str
    alt: str
    bounding_box: dict
    natural_width: int
    natural_height: int
    displayed_width: float
    displayed_height: float
    aspect_ratio: float


@dataclasses.dataclass
class SectionData:
    name: str
    y_start: float
    y_end: float
    crop_bytes: bytes


@dataclasses.dataclass
class PageData:
    url: str
    viewport: str
    viewport_size: tuple
    screenshot: bytes
    elements: list
    page_title: str
    all_text_content: str
    images: list
    sections: list
    failed_resources: Optional[list] = dataclasses.field(default_factory=list)
    console_errors: Optional[list] = dataclasses.field(default_factory=list)
    broken_images: Optional[list] = dataclasses.field(default_factory=list)
    performance_metrics: Optional[dict] = dataclasses.field(default_factory=dict)


EXTRACT_ELEMENTS_JS = """
() => {
    const selectors = 'h1,h2,h3,h4,h5,h6,p,span,a,button,div,section,header,footer,nav,main,article,ul,ol,li,label,input,textarea,select,table,th,td,form';
    const elements = document.querySelectorAll(selectors);

    function getSelector(el) {
        if (el.id) return el.tagName.toLowerCase() + '#' + el.id;
        let path = [];
        let current = el;
        while (current && current !== document.body && current !== document.documentElement) {
            let tag = current.tagName.toLowerCase();
            let parent = current.parentElement;
            if (parent) {
                let siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
                if (siblings.length > 1) {
                    let index = siblings.indexOf(current) + 1;
                    tag += ':nth-of-type(' + index + ')';
                }
            }
            path.unshift(tag);
            current = current.parentElement;
        }
        return path.join(' > ');
    }

    return Array.from(elements).filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }).slice(0, 500).map(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const scrollY = window.scrollY || window.pageYOffset;
        return {
            tag: el.tagName.toLowerCase(),
            selector: getSelector(el),
            text: (el.innerText || '').substring(0, 300).trim(),
            boundingBox: { x: rect.x, y: rect.y + scrollY, width: rect.width, height: rect.height },
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: style.fontWeight,
            fontStyle: style.fontStyle,
            lineHeight: style.lineHeight,
            letterSpacing: style.letterSpacing,
            textAlign: style.textAlign,
            color: style.color,
            margin: style.margin,
            padding: style.padding,
            position: style.position,
            display: style.display,
            textTransform: style.textTransform,
            backgroundColor: style.backgroundColor,
            border: style.border,
            textDecoration: style.textDecoration,
            ariaLabel: el.getAttribute('aria-label') || '',
            ariaRole: el.getAttribute('role') || '',
            tabIndex: el.hasAttribute('tabindex') ? el.getAttribute('tabindex') : ''
        };
    });
}
"""

EXTRACT_IMAGES_JS = """
() => {
    const imgs = document.querySelectorAll('img');
    const scrollY = window.scrollY || window.pageYOffset;
    return Array.from(imgs).filter(img => {
        const rect = img.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }).map(img => {
        const rect = img.getBoundingClientRect();
        return {
            src: img.src || '',
            alt: img.alt || '',
            boundingBox: { x: rect.x, y: rect.y + scrollY, width: rect.width, height: rect.height },
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
            displayedWidth: rect.width,
            displayedHeight: rect.height,
            aspectRatio: rect.width > 0 ? rect.width / rect.height : 0
        };
    });
}
"""


def crop_region(screenshot_bytes: bytes, x: float, y: float, w: float, h: float, padding: int = 20) -> bytes:
    img = Image.open(io.BytesIO(screenshot_bytes))
    left = max(0, int(x) - padding)
    top = max(0, int(y) - padding)
    right = min(img.width, int(x + w) + padding)
    bottom = min(img.height, int(y + h) + padding)
    if right <= left or bottom <= top:
        return screenshot_bytes
    cropped = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def detect_sections(elements: list, screenshot_bytes: bytes, page_height: int) -> list:
    section_tags = {"header", "nav", "main", "section", "article", "footer"}
    raw_sections = []

    for el in elements:
        if el.tag in section_tags and el.bounding_box.get("height", 0) > 50:
            raw_sections.append(el)

    if not raw_sections:
        chunk_h = min(800, page_height)
        sections = []
        y = 0
        idx = 1
        total_chunks = max(1, (page_height + chunk_h - 1) // chunk_h)
        while y < page_height:
            end = min(y + chunk_h, page_height)
            if y == 0:
                name = "Hero Banner / Top Area"
            elif end >= page_height - 10:
                name = "Footer / Bottom Area"
            elif idx <= 2:
                name = "Featured Content Area"
            elif idx >= total_chunks - 1:
                name = "Lower Content Area"
            else:
                name = f"Content Area {idx - 1}"
            crop = crop_region(screenshot_bytes, 0, y, 9999, end - y, padding=0)
            sections.append(SectionData(name=name, y_start=y, y_end=end, crop_bytes=crop))
            y = end
            idx += 1
        return sections

    raw_sections.sort(key=lambda e: e.bounding_box.get("y", 0))

    seen_ranges = []
    sections = []
    for el in raw_sections:
        bb = el.bounding_box
        y_s = bb.get("y", 0)
        y_e = y_s + bb.get("height", 0)

        overlaps = False
        for (sy, se) in seen_ranges:
            if y_s < se and y_e > sy:
                overlaps = True
                break
        if overlaps:
            continue

        name = _section_name(el.tag, el.text, y_s, page_height)
        crop = crop_region(screenshot_bytes, 0, y_s, 9999, bb.get("height", 200), padding=0)
        sections.append(SectionData(name=name, y_start=y_s, y_end=y_e, crop_bytes=crop))
        seen_ranges.append((y_s, y_e))

    return sections


SECTION_KEYWORDS = {
    "header": ["header", "top banner", "header area"],
    "navigation": ["navigation", "nav", "menu"],
    "hero": ["hero", "banner", "top banner"],
    "content": ["content", "main", "article", "product", "section"],
    "footer": ["footer", "bottom"],
    "images": [],
}


def _section_name(tag: str, text: str, y_pos: float, page_height: float) -> str:
    if tag == "header":
        return "Header"
    if tag == "nav":
        return "Navigation Menu"
    if tag == "footer":
        return "Footer"
    if y_pos < 200:
        return "Top Banner / Header Area"
    if y_pos > page_height * 0.85:
        return "Footer Area"

    snippet = (text or "")[:40].strip()
    if snippet:
        return f"Content Section - \"{snippet}...\""
    return "Content Section"


def find_section_by_keyword(sections: list, keyword: str, page_height: int) -> tuple:
    keyword = keyword.lower().strip()

    if keyword == "all":
        return 0, page_height

    if keyword in SECTION_KEYWORDS:
        match_terms = SECTION_KEYWORDS[keyword]
    else:
        match_terms = [keyword]

    for sec in sections:
        sec_lower = sec.name.lower()
        for term in match_terms:
            if term in sec_lower:
                return sec.y_start, sec.y_end

    fallbacks = {
        "header": (0, min(300, page_height)),
        "navigation": (0, min(200, page_height)),
        "hero": (0, min(800, page_height)),
        "footer": (max(0, page_height - 600), page_height),
        "content": (200, max(200, page_height - 400)),
    }
    if keyword in fallbacks:
        return fallbacks[keyword]

    return 0, page_height


def filter_elements_by_range(elements: list, y_start: float, y_end: float) -> list:
    filtered = []
    for el in elements:
        el_y = el.bounding_box.get("y", 0)
        el_bottom = el_y + el.bounding_box.get("height", 0)
        if el_bottom > y_start and el_y < y_end:
            filtered.append(el)
    return filtered


def filter_images_by_range(images: list, y_start: float, y_end: float) -> list:
    filtered = []
    for img in images:
        img_y = img.bounding_box.get("y", 0)
        img_bottom = img_y + img.bounding_box.get("height", 0)
        if img_bottom > y_start and img_y < y_end:
            filtered.append(img)
    return filtered


def _infer_resource_type(url: str, content_type: str = "") -> str:
    ct = content_type.lower()
    if "image" in ct or any(url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
        return "image"
    if "font" in ct or any(url.lower().endswith(ext) for ext in (".woff", ".woff2", ".ttf", ".otf", ".eot")):
        return "font"
    if "css" in ct or url.lower().endswith(".css"):
        return "stylesheet"
    if "javascript" in ct or url.lower().endswith(".js"):
        return "script"
    return "other"


SETUP_PERFORMANCE_OBSERVER_JS = """
() => {
    window.__cls_entries = [];
    window.__lcp_value = 0;
    window.__lcp_element = '';
    try {
        new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) {
                    window.__cls_entries.push({ value: entry.value });
                }
            }
        }).observe({type: 'layout-shift', buffered: true});
    } catch(e) {}
    try {
        new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                window.__lcp_value = entry.startTime;
                window.__lcp_element = entry.element ? entry.element.tagName : '';
            }
        }).observe({type: 'largest-contentful-paint', buffered: true});
    } catch(e) {}
}
"""

COLLECT_PERFORMANCE_JS = """
() => {
    let cls = 0;
    (window.__cls_entries || []).forEach(e => { cls += e.value; });
    const resources = performance.getEntriesByType('resource').filter(r => r.duration > 1000).map(r => ({
        url: r.name,
        duration: Math.round(r.duration),
        size: r.transferSize || 0,
        type: r.initiatorType
    }));
    return {
        cls_score: cls,
        lcp_ms: window.__lcp_value || 0,
        lcp_element: window.__lcp_element || '',
        slow_resources: resources
    };
}
"""

CHECK_BROKEN_IMAGES_JS = """
() => {
    return Array.from(document.querySelectorAll('img')).filter(img => {
        const rect = img.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && (!img.complete || img.naturalWidth === 0);
    }).map(img => ({ src: img.src || '', alt: img.alt || '' }));
}
"""


def scroll_to_load(page: Page, wait_ms: int = 400):
    viewport_height = page.evaluate("() => window.innerHeight")
    total_height = page.evaluate("() => document.body.scrollHeight")
    current = 0
    while current < total_height:
        current += viewport_height
        page.evaluate(f"window.scrollTo(0, {current})")
        page.wait_for_timeout(wait_ms)
        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height > total_height:
            total_height = new_height
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def scrape_page(browser: Browser, url: str, viewport_name: str, viewport_size: dict,
                wait_seconds: int = 2, enable_scroll: bool = True,
                collect_network: bool = True, collect_performance: bool = True) -> PageData:
    context = browser.new_context(viewport=viewport_size)
    page = context.new_page()

    failed_resources = []
    console_errors = []

    if collect_network:
        def on_response(response):
            try:
                if response.status >= 400:
                    ct = response.headers.get("content-type", "")
                    failed_resources.append(NetworkIssue(
                        url=response.url,
                        resource_type=_infer_resource_type(response.url, ct),
                        status_code=response.status,
                        error_text=f"HTTP {response.status}",
                    ))
            except Exception:
                pass

        def on_request_failed(request):
            try:
                failed_resources.append(NetworkIssue(
                    url=request.url,
                    resource_type=_infer_resource_type(request.url),
                    status_code=0,
                    error_text=request.failure or "Request failed",
                ))
            except Exception:
                pass

        def on_console(msg):
            try:
                if msg.type in ("error", "warning"):
                    console_errors.append({"text": msg.text, "type": msg.type})
            except Exception:
                pass

        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)
        page.on("console", on_console)

    try:
        if collect_performance:
            page.add_init_script(SETUP_PERFORMANCE_OBSERVER_JS.strip().removeprefix("(").removesuffix(")").strip())

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
        page.wait_for_timeout(wait_seconds * 1000)

        if collect_performance:
            try:
                page.evaluate(SETUP_PERFORMANCE_OBSERVER_JS)
            except Exception:
                pass

        if enable_scroll:
            scroll_to_load(page)

        screenshot = page.screenshot(full_page=True)

        raw_elements = page.evaluate(EXTRACT_ELEMENTS_JS)
        elements = [
            ElementData(
                tag=e["tag"],
                selector=e["selector"],
                text=e["text"],
                bounding_box=e["boundingBox"],
                font_family=e["fontFamily"],
                font_size=e["fontSize"],
                font_weight=e["fontWeight"],
                font_style=e["fontStyle"],
                line_height=e["lineHeight"],
                letter_spacing=e["letterSpacing"],
                text_align=e["textAlign"],
                color=e["color"],
                margin=e["margin"],
                padding=e["padding"],
                position=e["position"],
                display=e["display"],
                text_transform=e["textTransform"],
                background_color=e["backgroundColor"],
                border=e["border"],
                text_decoration=e["textDecoration"],
                aria_label=e.get("ariaLabel", ""),
                aria_role=e.get("ariaRole", ""),
                tab_index=e.get("tabIndex", ""),
            )
            for e in raw_elements
        ]

        raw_images = page.evaluate(EXTRACT_IMAGES_JS)
        images = [
            ImageData(
                src=img["src"],
                alt=img["alt"],
                bounding_box=img["boundingBox"],
                natural_width=img["naturalWidth"],
                natural_height=img["naturalHeight"],
                displayed_width=img["displayedWidth"],
                displayed_height=img["displayedHeight"],
                aspect_ratio=img["aspectRatio"],
            )
            for img in raw_images
        ]

        broken_images = []
        try:
            broken_images = page.evaluate(CHECK_BROKEN_IMAGES_JS)
        except Exception:
            pass

        perf_metrics = {}
        if collect_performance:
            try:
                perf_metrics = page.evaluate(COLLECT_PERFORMANCE_JS)
            except Exception:
                pass

        page_title = page.title()
        all_text = page.evaluate("() => document.body.innerText || ''")
        page_height = page.evaluate("() => document.body.scrollHeight")

        sections = detect_sections(elements, screenshot, page_height)

        return PageData(
            url=url,
            viewport=viewport_name,
            viewport_size=(viewport_size["width"], viewport_size["height"]),
            screenshot=screenshot,
            elements=elements,
            page_title=page_title,
            all_text_content=all_text,
            images=images,
            sections=sections,
            failed_resources=failed_resources,
            console_errors=console_errors,
            broken_images=broken_images,
            performance_metrics=perf_metrics,
        )
    finally:
        context.close()
