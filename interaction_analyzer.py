import io
import numpy as np
from PIL import Image
from playwright.sync_api import Page
from analyzer import Difference
from scraper import ElementData, crop_region


def capture_and_compare_hover_states(page: Page, elements: list, screenshot: bytes,
                                     sections: list, url: str, page_label: str = "Page",
                                     max_elements: int = 20) -> list:
    diffs = []
    interactive = [el for el in elements if el.tag in ("button", "a") and el.text.strip()]
    interactive = interactive[:max_elements]

    for el in interactive:
        try:
            bb = el.bounding_box
            cx = bb["x"] + bb["width"] / 2
            cy = bb["y"] + bb["height"] / 2

            page.evaluate("window.scrollTo(0, 0)")

            viewport_h = page.evaluate("() => window.innerHeight")
            if cy > viewport_h:
                page.evaluate(f"window.scrollTo(0, {int(cy - viewport_h / 2)})")
                page.wait_for_timeout(200)

            before_crop = _capture_element_crop(page, bb)
            if not before_crop:
                continue

            visible_cy = cy - page.evaluate("() => window.scrollY")
            page.mouse.move(bb["x"] + bb["width"] / 2, visible_cy)
            page.wait_for_timeout(300)

            after_crop = _capture_element_crop(page, bb)

            page.mouse.move(0, 0)

            if before_crop and after_crop:
                has_hover = _images_differ(before_crop, after_crop)
                if not has_hover:
                    diffs.append(Difference(
                        category="Interaction States",
                        severity="minor",
                        element=el.selector,
                        property="hover-state-missing",
                        value1="No hover effect detected",
                        value2="Interactive elements should have visual hover feedback",
                        description=f"No hover effect on {el.tag}: {el.text[:50]}",
                        human_description=f"[{page_label}] This {el.tag} (\"{el.text[:40]}\") has no visible hover effect. Users can't tell it's clickable when they move their mouse over it.",
                        section_name=_find_section(sections, bb.get("y", 0)),
                        element_name=f"{el.tag} \"{el.text[:40]}\"",
                        navigation=f"Hover your mouse over \"{el.text[:60]}\"",
                        crop1_bytes=before_crop,
                        crop2_bytes=b"",
                    ))
        except Exception:
            continue

    page.evaluate("window.scrollTo(0, 0)")
    return diffs


def compare_hover_states_cross_page(page1: Page, page2: Page,
                                     elements1: list, elements2: list,
                                     screenshot1: bytes, screenshot2: bytes,
                                     sections1: list, sections2: list) -> list:
    diffs = []

    matched = _match_interactive_elements(elements1, elements2)

    for el1, el2 in matched[:10]:
        try:
            has_hover1 = _test_hover(page1, el1)
            has_hover2 = _test_hover(page2, el2)

            if has_hover1 and not has_hover2:
                crop1 = b""
                try:
                    bb = el1.bounding_box
                    crop1 = crop_region(screenshot1, bb["x"], bb["y"], bb["width"], bb["height"])
                except Exception:
                    pass

                diffs.append(Difference(
                    category="Interaction States",
                    severity="major",
                    element=el1.selector,
                    property="hover-state-mismatch",
                    value1="Live: has hover effect",
                    value2="UAT: no hover effect",
                    description=f"Hover effect present on Live but missing on UAT for {el1.tag}: {el1.text[:50]}",
                    human_description=f"This {el1.tag} (\"{el1.text[:40]}\") has a hover effect on Live but not on UAT. The UAT version should match.",
                    section_name=_find_section(sections1, el1.bounding_box.get("y", 0)),
                    element_name=f"{el1.tag} \"{el1.text[:40]}\"",
                    navigation=f"Hover over \"{el1.text[:60]}\" on both Live and UAT to compare",
                    crop1_bytes=crop1,
                    crop2_bytes=b"",
                ))
        except Exception:
            continue

    return diffs


def _capture_element_crop(page: Page, bb: dict) -> bytes:
    try:
        scroll_y = page.evaluate("() => window.scrollY")
        screenshot = page.screenshot()
        visible_y = bb["y"] - scroll_y
        return crop_region(screenshot, bb["x"], visible_y, bb["width"], bb["height"], padding=5)
    except Exception:
        return b""


def _images_differ(img1_bytes: bytes, img2_bytes: bytes, threshold: float = 5.0) -> bool:
    try:
        img1 = np.array(Image.open(io.BytesIO(img1_bytes)).convert("RGB"))
        img2 = np.array(Image.open(io.BytesIO(img2_bytes)).convert("RGB"))
        if img1.shape != img2.shape:
            return True
        diff = np.mean(np.abs(img1.astype(float) - img2.astype(float)))
        return diff > threshold
    except Exception:
        return False


def _test_hover(page: Page, el: ElementData) -> bool:
    try:
        bb = el.bounding_box
        viewport_h = page.evaluate("() => window.innerHeight")
        cy = bb["y"] + bb["height"] / 2
        if cy > viewport_h:
            page.evaluate(f"window.scrollTo(0, {int(cy - viewport_h / 2)})")
            page.wait_for_timeout(200)

        before = _capture_element_crop(page, bb)
        visible_cy = cy - page.evaluate("() => window.scrollY")
        page.mouse.move(bb["x"] + bb["width"] / 2, visible_cy)
        page.wait_for_timeout(300)
        after = _capture_element_crop(page, bb)
        page.mouse.move(0, 0)
        page.evaluate("window.scrollTo(0, 0)")

        return _images_differ(before, after)
    except Exception:
        return False


def _match_interactive_elements(elements1: list, elements2: list) -> list:
    matched = []
    interactive_tags = {"button", "a"}

    e1_list = [e for e in elements1 if e.tag in interactive_tags and e.text.strip()]
    e2_map = {}
    for e in elements2:
        if e.tag in interactive_tags and e.text.strip():
            key = (e.tag, e.text.strip()[:50])
            e2_map[key] = e

    for e1 in e1_list:
        key = (e1.tag, e1.text.strip()[:50])
        if key in e2_map:
            matched.append((e1, e2_map[key]))

    return matched


def _find_section(sections: list, y_pos: float) -> str:
    for sec in sections:
        if sec.y_start <= y_pos <= sec.y_end:
            return sec.name
    return "Page"
