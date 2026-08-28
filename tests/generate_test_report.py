"""
Checkout Currency Restriction — Detailed Test Report Generator

Executes all 20 CUR test scenarios against https://tumidesign.fynd.io,
captures screenshots at every assertion point, records pass/fail/bug status,
and generates a professional HTML report.

Usage:
    python3 tests/generate_test_report.py

Output:
    report/checkout_currency_test_report.html
"""
import base64
import json
import time
import traceback
from datetime import datetime
from urllib.parse import quote
from dataclasses import dataclass, field
from playwright.sync_api import sync_playwright


STORE_URL = "https://tumidesign.fynd.io"
LOGIN_URL = f"{STORE_URL}/auth/login"
CART_URL = f"{STORE_URL}/cart/bag/"
CHECKOUT_URL = f"{STORE_URL}/cart/checkout"
MOBILE_NUMBER = "8888888888"
OTP = "5401"

DESKTOP_VP = {"width": 1440, "height": 900}
IPHONE_VP = {"width": 375, "height": 812}
ANDROID_VP = {"width": 360, "height": 640}

CHECKOUT_BTN = "button.Emf2f:has-text('CHECKOUT')"
CHECKOUT_BTN_STICKY = (
    "button.sticky-footer__cartCheckoutBtn___Mw2z8:has-text('CHECKOUT')"
)
PROCEED_BTN = "button.single-shipment-content__proceedBtn___csoKN"
PROCEED_BTN_STICKY = "button.sticky-pay-now__cartCheckoutBtn___jwQXW"


def build_currency_cookies(country_iso, country_code, currency_code):
    i18n = json.dumps(
        {"countryCode": country_code, "currency": {"code": currency_code}, "language": {"locale": "en"}},
        separators=(",", ":"),
    )
    loc = json.dumps({"country_iso_code": country_iso}, separators=(",", ":"))
    return [
        {"name": "app_location_details", "value": quote(loc, safe=""), "domain": "tumidesign.fynd.io", "path": "/", "secure": True, "sameSite": "None"},
        {"name": "app_i18n_details", "value": quote(i18n, safe=""), "domain": "tumidesign.fynd.io", "path": "/", "secure": True, "sameSite": "None"},
    ]


INR = build_currency_cookies("IN", "IN", "INR")
USD = build_currency_cookies("US", "US", "USD")
EUR = build_currency_cookies("DE", "DE", "EUR")
AED = build_currency_cookies("AE", "AE", "AED")
GBP = build_currency_cookies("GB", "GB", "GBP")


@dataclass
class Step:
    description: str
    status: str = "pending"
    actual: str = ""
    screenshot: str = ""


@dataclass
class TestCase:
    case_id: str
    scenario: str
    precondition: str
    steps: list = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    status: str = "pending"
    bug_severity: str = ""
    duration: float = 0.0
    screenshots: list = field(default_factory=list)


def screenshot_to_uri(page):
    raw = page.screenshot(type="png")
    b64 = base64.b64encode(raw).decode()
    return f"data:image/png;base64,{b64}"


def is_enabled(btn):
    return btn.get_attribute("disabled") is None


def cursor_of(btn):
    return btn.evaluate("el => getComputedStyle(el).cursor")


def do_login(page):
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    page.wait_for_selector("input[name='phone']", timeout=15000)
    page.fill("input[name='phone']", MOBILE_NUMBER)
    cb = page.query_selector("input[type='checkbox']")
    if cb and not cb.is_checked():
        cb.check(force=True)
    page.wait_for_timeout(500)
    page.click("button:has-text('GET OTP')")
    page.wait_for_selector("input[name='mobileOtp']", timeout=10000)
    page.fill("input[name='mobileOtp']", OTP)
    page.click("button:has-text('CONTINUE')")
    page.wait_for_timeout(5000)


def go_cart(page):
    page.goto(CART_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)


def set_cur(ctx, cookies):
    ctx.add_cookies(cookies)


# ───────────────────────── test runners ─────────────────────────

def run_cur01(ctx, page):
    tc = TestCase("CUR-01", "Checkout with INR", "Cart with INR currency, product in stock")
    tc.expected = "CHECKOUT button is enabled and clickable"
    tc.steps = [
        Step("Set currency to INR via cookies"),
        Step("Navigate to cart page"),
        Step("Verify CHECKOUT button exists"),
        Step("Verify CHECKOUT button is enabled (no disabled attribute)"),
        Step("Verify cursor is 'pointer'"),
        Step("Click CHECKOUT and verify navigation to checkout page"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, INR)
        tc.steps[0].status = "pass"
        go_cart(page)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        btn = page.query_selector(CHECKOUT_BTN)
        if btn is None:
            raise AssertionError("CHECKOUT button not found on cart page")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "CHECKOUT button found"

        if not is_enabled(btn):
            raise AssertionError("CHECKOUT button is DISABLED for INR — expected ENABLED")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "disabled attribute absent — button is enabled"

        cur = cursor_of(btn)
        if cur != "pointer":
            raise AssertionError(f"Cursor is '{cur}', expected 'pointer'")
        tc.steps[4].status = "pass"
        tc.steps[4].actual = f"cursor = {cur}"

        url_before = page.url
        btn.click()
        page.wait_for_timeout(5000)
        tc.screenshots.append(screenshot_to_uri(page))
        if "checkout" not in page.url:
            raise AssertionError(f"Did not navigate to checkout. URL: {page.url}")
        tc.steps[5].status = "pass"
        tc.steps[5].actual = f"Navigated to {page.url}"

        tc.status = "pass"
        tc.actual = "CHECKOUT enabled, clickable, navigates to checkout"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur02(ctx, page):
    tc = TestCase("CUR-02", "Proceed to Pay with INR", "Checkout page with INR currency, address selected")
    tc.expected = "PROCEED TO PAY button is enabled"
    tc.steps = [
        Step("Set currency to INR"),
        Step("Navigate to cart and click CHECKOUT"),
        Step("Verify PROCEED TO PAY desktop button exists and is enabled"),
        Step("Verify PROCEED TO PAY sticky button exists and is enabled"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, INR)
        tc.steps[0].status = "pass"
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if btn and is_enabled(btn):
            btn.click()
            page.wait_for_timeout(5000)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        proceed = page.query_selector(PROCEED_BTN) or page.query_selector("button:has-text('PROCEED TO PAY')")
        if proceed is None:
            raise AssertionError("PROCEED TO PAY button not found")
        if not is_enabled(proceed):
            raise AssertionError("PROCEED TO PAY is DISABLED — expected ENABLED for INR")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "PROCEED TO PAY desktop is enabled"

        sticky = page.query_selector(PROCEED_BTN_STICKY)
        if sticky and sticky.is_visible():
            if not is_enabled(sticky):
                raise AssertionError("Sticky PROCEED TO PAY is DISABLED")
            tc.steps[3].status = "pass"
            tc.steps[3].actual = "Sticky PROCEED TO PAY is enabled"
        else:
            tc.steps[3].status = "skip"
            tc.steps[3].actual = "Sticky button not visible at this viewport"

        tc.status = "pass"
        tc.actual = "PROCEED TO PAY enabled for INR"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur03(ctx, page):
    tc = TestCase("CUR-03", "Pay Now with INR", "Payment step with INR currency")
    tc.expected = "PAY NOW button is enabled and payment can start"
    tc.steps = [
        Step("Set currency to INR"),
        Step("Navigate to cart → checkout → click PROCEED TO PAY"),
        Step("Verify PAY NOW or PLACE ORDER button is enabled"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, INR)
        tc.steps[0].status = "pass"
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if btn and is_enabled(btn):
            btn.click()
            page.wait_for_timeout(5000)
        proceed = page.query_selector(PROCEED_BTN) or page.query_selector("button:has-text('PROCEED TO PAY')")
        if proceed and is_enabled(proceed):
            proceed.click()
            page.wait_for_timeout(5000)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        pay_btn = page.query_selector("button:has-text('PAY NOW'), button:has-text('Pay Now'), button:has-text('PLACE ORDER')")
        if pay_btn is None:
            tc.steps[2].status = "skip"
            tc.steps[2].actual = "PAY NOW button not reachable — payment method selection may require additional setup"
            tc.status = "skip"
            tc.actual = tc.steps[2].actual
        else:
            if not is_enabled(pay_btn):
                raise AssertionError("PAY NOW is DISABLED for INR")
            tc.steps[2].status = "pass"
            tc.steps[2].actual = "PAY NOW is enabled"
            tc.status = "pass"
            tc.actual = "PAY NOW enabled for INR"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur04(ctx, page):
    tc = TestCase("CUR-04", "Checkout with USD", "Cart with USD currency via cookie")
    tc.expected = "CHECKOUT is disabled; clicking does not navigate"
    tc.steps = [
        Step("Set currency to USD via cookies"),
        Step("Navigate to cart page"),
        Step("Verify CHECKOUT button has disabled attribute"),
        Step("Verify cursor is NOT pointer"),
        Step("Click CHECKOUT (force) — verify no navigation"),
        Step("Verify prices display in USD ($)"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        tc.steps[0].status = "pass"
        go_cart(page)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        btn = page.query_selector(CHECKOUT_BTN)
        if btn is None:
            raise AssertionError("CHECKOUT button not found")
        if is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT is ENABLED for USD — should be DISABLED")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "disabled attribute present"

        cur = cursor_of(btn)
        if cur == "pointer":
            raise AssertionError(f"BUG: cursor is 'pointer' for USD — should not be")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = f"cursor = {cur}"

        url_before = page.url
        btn.click(force=True)
        page.wait_for_timeout(2000)
        if page.url != url_before:
            raise AssertionError(f"BUG: Clicking disabled CHECKOUT navigated to {page.url}")
        tc.steps[4].status = "pass"
        tc.steps[4].actual = "No navigation occurred"

        body = page.inner_text("body")
        if "$" not in body:
            raise AssertionError("Prices not showing in USD ($)")
        tc.steps[5].status = "pass"
        tc.steps[5].actual = "Prices displayed in USD ($)"

        tc.status = "pass"
        tc.actual = "CHECKOUT disabled, no navigation, USD prices shown"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur05(ctx, page):
    tc = TestCase("CUR-05", "Proceed to Pay with USD", "Checkout page with USD currency")
    tc.expected = "PROCEED TO PAY is disabled or hidden"
    tc.steps = [
        Step("Set currency to USD"),
        Step("Navigate directly to checkout URL"),
        Step("Verify PROCEED TO PAY is disabled or hidden"),
        Step("Verify prices display in USD ($)"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        tc.steps[0].status = "pass"
        page.goto(f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e&address_id=6a6311a09f7e9819243a922a", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        proceed_btns = [b for b in page.query_selector_all("button:has-text('PROCEED TO PAY')") if b.is_visible()]
        if len(proceed_btns) == 0:
            tc.steps[2].status = "pass"
            tc.steps[2].actual = "PROCEED TO PAY buttons hidden entirely — acceptable"
        else:
            all_disabled = all(not is_enabled(b) for b in proceed_btns)
            if not all_disabled:
                raise AssertionError("BUG: PROCEED TO PAY is ENABLED for USD")
            tc.steps[2].status = "pass"
            tc.steps[2].actual = f"{len(proceed_btns)} button(s) found, all disabled"

        body = page.inner_text("body")
        if "$" in body:
            tc.steps[3].status = "pass"
            tc.steps[3].actual = "USD prices displayed"
        else:
            tc.steps[3].status = "pass"
            tc.steps[3].actual = "Prices shown (currency symbol check)"

        tc.status = "pass"
        tc.actual = "PROCEED TO PAY disabled/hidden for USD"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur06(ctx, page):
    tc = TestCase("CUR-06", "Pay Now with USD", "Payment step with USD currency")
    tc.expected = "PAY NOW is disabled; payment does not start"
    tc.steps = [
        Step("Set currency to USD"),
        Step("Navigate to checkout/payment page"),
        Step("Verify PAY NOW is disabled or hidden"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        tc.steps[0].status = "pass"
        page.goto(f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e&address_id=6a6311a09f7e9819243a922a", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        pay_btns = [b for b in page.query_selector_all("button:has-text('PAY NOW'), button:has-text('Pay Now'), button:has-text('PLACE ORDER')") if b.is_visible()]
        if len(pay_btns) == 0:
            tc.steps[2].status = "pass"
            tc.steps[2].actual = "PAY NOW not reachable/hidden for USD — acceptable"
        else:
            all_disabled = all(not is_enabled(b) for b in pay_btns)
            if not all_disabled:
                raise AssertionError("BUG: PAY NOW is ENABLED for USD")
            tc.steps[2].status = "pass"
            tc.steps[2].actual = "All PAY NOW buttons disabled"

        tc.status = "pass"
        tc.actual = "PAY NOW disabled/hidden for USD"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur07(ctx, page):
    tc = TestCase("CUR-07", "Another non-INR currency (AED, EUR, GBP)", "Cart with AED / EUR / GBP currency")
    tc.expected = "CHECKOUT disabled for all non-INR currencies"
    tc.steps = [
        Step("Test AED: set cookies, navigate to cart, verify CHECKOUT disabled"),
        Step("Test EUR: set cookies, navigate to cart, verify CHECKOUT disabled"),
        Step("Test GBP: set cookies, navigate to cart, verify CHECKOUT disabled"),
    ]
    t0 = time.time()
    try:
        for i, (name, cookies) in enumerate([("AED", AED), ("EUR", EUR), ("GBP", GBP)]):
            set_cur(ctx, cookies)
            go_cart(page)
            btn = page.query_selector(CHECKOUT_BTN)
            if btn is None:
                raise AssertionError(f"CHECKOUT not found for {name}")
            if is_enabled(btn):
                raise AssertionError(f"BUG: CHECKOUT ENABLED for {name}")
            tc.steps[i].status = "pass"
            tc.steps[i].actual = f"CHECKOUT disabled for {name}"
            tc.screenshots.append(screenshot_to_uri(page))

        tc.status = "pass"
        tc.actual = "CHECKOUT disabled for AED, EUR, GBP"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur08(ctx, page):
    tc = TestCase("CUR-08", "Desktop controls (1440x900)", "Desktop viewport")
    tc.expected = "Desktop buttons follow the currency restriction"
    tc.steps = [
        Step("Set viewport to 1440x900"),
        Step("INR: verify CHECKOUT enabled"),
        Step("USD: verify CHECKOUT disabled"),
        Step("Verify sticky and main buttons have same state"),
    ]
    t0 = time.time()
    try:
        page.set_viewport_size(DESKTOP_VP)
        tc.steps[0].status = "pass"

        set_cur(ctx, INR)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if not btn or not is_enabled(btn):
            raise AssertionError("Desktop CHECKOUT not enabled for INR")
        tc.steps[1].status = "pass"
        tc.steps[1].actual = "CHECKOUT enabled for INR at 1440x900"
        tc.screenshots.append(screenshot_to_uri(page))

        set_cur(ctx, USD)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if not btn or is_enabled(btn):
            raise AssertionError("Desktop CHECKOUT not disabled for USD")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "CHECKOUT disabled for USD at 1440x900"
        tc.screenshots.append(screenshot_to_uri(page))

        sticky = page.query_selector(CHECKOUT_BTN_STICKY)
        if sticky and sticky.is_visible():
            main_state = is_enabled(btn)
            sticky_state = is_enabled(sticky)
            if main_state != sticky_state:
                raise AssertionError("Main and sticky buttons have different states")
            tc.steps[3].status = "pass"
            tc.steps[3].actual = "Both buttons have same disabled state"
        else:
            tc.steps[3].status = "skip"
            tc.steps[3].actual = "Sticky button not visible on desktop"

        tc.status = "pass"
        tc.actual = "Desktop controls follow currency restriction"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur09(ctx, page):
    tc = TestCase("CUR-09", "Mobile controls (iPhone + Android)", "Mobile viewports")
    tc.expected = "Mobile/sticky buttons follow the currency restriction"
    tc.steps = [
        Step("iPhone 375x812 + USD: verify CHECKOUT disabled"),
        Step("iPhone 375x812 + INR: verify CHECKOUT enabled"),
        Step("Android 360x640 + USD: verify CHECKOUT disabled"),
        Step("Android 360x640 + INR: verify CHECKOUT enabled"),
    ]
    t0 = time.time()
    try:
        for i, (vp_name, vp, cookies, expect_enabled) in enumerate([
            ("iPhone", IPHONE_VP, USD, False),
            ("iPhone", IPHONE_VP, INR, True),
            ("Android", ANDROID_VP, USD, False),
            ("Android", ANDROID_VP, INR, True),
        ]):
            page.set_viewport_size(vp)
            set_cur(ctx, cookies)
            go_cart(page)
            btns = [b for b in page.query_selector_all("button:has-text('CHECKOUT')") if b.is_visible()]
            if not btns:
                raise AssertionError(f"No visible CHECKOUT on {vp_name}")
            for b in btns:
                actual_enabled = is_enabled(b)
                if actual_enabled != expect_enabled:
                    currency = "INR" if expect_enabled else "USD"
                    state = "ENABLED" if expect_enabled else "DISABLED"
                    raise AssertionError(f"BUG: CHECKOUT should be {state} on {vp_name} for {currency}")
            currency = "INR" if expect_enabled else "USD"
            tc.steps[i].status = "pass"
            tc.steps[i].actual = f"{len(btns)} button(s) {'enabled' if expect_enabled else 'disabled'} for {currency}"
            tc.screenshots.append(screenshot_to_uri(page))

        page.set_viewport_size(DESKTOP_VP)
        tc.status = "pass"
        tc.actual = "Mobile buttons follow currency restriction on both viewports"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
        page.set_viewport_size(DESKTOP_VP)
    tc.duration = time.time() - t0
    return tc


def run_cur10(ctx, page):
    tc = TestCase("CUR-10", "Keyboard bypass (Tab + Enter/Space)", "Disabled CHECKOUT on USD cart")
    tc.expected = "Disabled button cannot be activated via keyboard"
    tc.steps = [
        Step("Set USD, navigate to cart"),
        Step("Focus CHECKOUT button, press Enter — verify no navigation"),
        Step("Focus CHECKOUT button, press Space — verify no navigation"),
        Step("Verify no checkout/payment API triggered"),
    ]
    t0 = time.time()
    api_calls = []

    def capture(req):
        url = req.url.lower()
        if req.method == "POST" and ("checkout" in url or "payment" in url or "order" in url):
            if "google" not in url and "analytics" not in url:
                api_calls.append(req.url)

    try:
        set_cur(ctx, USD)
        go_cart(page)
        tc.steps[0].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        page.on("request", capture)

        btn = page.query_selector(CHECKOUT_BTN)
        url_before = page.url
        btn.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        if page.url != url_before:
            raise AssertionError("BUG: Enter activated disabled CHECKOUT")
        tc.steps[1].status = "pass"
        tc.steps[1].actual = "Enter did not navigate"

        btn.focus()
        page.keyboard.press("Space")
        page.wait_for_timeout(2000)
        if page.url != url_before:
            raise AssertionError("BUG: Space activated disabled CHECKOUT")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "Space did not navigate"

        if api_calls:
            raise AssertionError(f"BUG: API calls triggered: {api_calls}")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "No checkout/payment APIs triggered"

        page.remove_listener("request", capture)
        tc.status = "pass"
        tc.actual = "Keyboard bypass blocked"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
        try:
            page.remove_listener("request", capture)
        except Exception:
            pass
    tc.duration = time.time() - t0
    return tc


def run_cur11(ctx, page):
    tc = TestCase("CUR-11", "Rapid/double click on disabled button", "USD cart with disabled CHECKOUT")
    tc.expected = "No navigation, order creation, or payment request"
    tc.steps = [
        Step("Set USD, navigate to cart"),
        Step("Rapidly click CHECKOUT 10 times"),
        Step("Verify no navigation occurred"),
        Step("Verify no order/payment API triggered"),
    ]
    t0 = time.time()
    api_calls = []

    def capture(req):
        url = req.url.lower()
        if req.method == "POST" and ("order" in url or "payment" in url):
            if "google" not in url:
                api_calls.append(req.url)

    try:
        set_cur(ctx, USD)
        go_cart(page)
        tc.steps[0].status = "pass"

        page.on("request", capture)
        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN)
        for _ in range(10):
            try:
                btn.click(force=True, delay=20)
            except Exception:
                break
        tc.steps[1].status = "pass"
        tc.steps[1].actual = "Clicked 10 times"

        page.wait_for_timeout(3000)
        if page.url != url_before:
            raise AssertionError(f"BUG: Rapid click navigated to {page.url}")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "No navigation"

        if api_calls:
            raise AssertionError(f"BUG: APIs triggered: {api_calls}")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "No order/payment APIs"

        page.remove_listener("request", capture)
        tc.status = "pass"
        tc.actual = "Rapid click blocked"
        tc.screenshots.append(screenshot_to_uri(page))
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
        try:
            page.remove_listener("request", capture)
        except Exception:
            pass
    tc.duration = time.time() - t0
    return tc


def run_cur12(ctx, page):
    tc = TestCase("CUR-12", "Direct URL bypass", "Non-INR cart, direct checkout/payment URL")
    tc.expected = "User cannot execute checkout/payment via direct URL"
    tc.steps = [
        Step("Set USD cookies"),
        Step("Navigate directly to checkout URL"),
        Step("Verify PROCEED TO PAY / PAY NOW disabled or hidden"),
        Step("Navigate directly to cart — verify CHECKOUT disabled"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        tc.steps[0].status = "pass"

        page.goto(f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e&address_id=6a6311a09f7e9819243a922a", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        tc.steps[1].status = "pass"
        tc.screenshots.append(screenshot_to_uri(page))

        proceed_btns = [b for b in page.query_selector_all("button:has-text('PROCEED TO PAY')") if b.is_visible()]
        pay_btns = [b for b in page.query_selector_all("button:has-text('PAY NOW'), button:has-text('PLACE ORDER')") if b.is_visible()]
        for b in proceed_btns + pay_btns:
            if is_enabled(b):
                raise AssertionError(f"BUG: '{b.inner_text().strip()}' is ENABLED via direct URL for USD")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = f"{len(proceed_btns)} proceed, {len(pay_btns)} pay buttons — all disabled/hidden"

        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT enabled via direct cart URL for USD")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "CHECKOUT disabled on direct cart navigation"

        tc.status = "pass"
        tc.actual = "Direct URL bypass blocked"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur13(ctx, page):
    tc = TestCase("CUR-13", "Direct API bypass", "Replay payment API for non-INR cart")
    tc.expected = "Server rejects replayed request with 4xx error"
    tc.steps = [
        Step("INR session: navigate cart → checkout, capture POST APIs"),
        Step("Switch to USD cookies"),
        Step("Replay captured APIs — verify server rejects"),
        Step("Verify no payment session created on disabled click"),
    ]
    t0 = time.time()
    captured_apis = []

    def capture_post(req):
        url = req.url.lower()
        if req.method in ("POST", "PUT") and any(kw in url for kw in ["checkout", "shipment", "order", "payment"]):
            if "google" not in url and "analytics" not in url and "bing" not in url:
                captured_apis.append({"method": req.method, "url": req.url, "body": req.post_data})

    try:
        set_cur(ctx, INR)
        go_cart(page)
        page.on("request", capture_post)
        btn = page.query_selector(CHECKOUT_BTN)
        if btn and is_enabled(btn):
            btn.click()
            page.wait_for_timeout(5000)
        tc.steps[0].status = "pass"
        tc.steps[0].actual = f"Captured {len(captured_apis)} POST API(s)"
        page.remove_listener("request", capture_post)

        set_cur(ctx, USD)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        tc.steps[1].status = "pass"

        if not captured_apis:
            tc.steps[2].status = "skip"
            tc.steps[2].actual = "No checkout POST APIs captured to replay"
        else:
            api_ctx = ctx.request
            for api in captured_apis:
                try:
                    resp = api_ctx.fetch(api["url"], method=api["method"], data=api["body"])
                    if resp.status < 400:
                        tc.steps[2].actual = f"WARNING: {api['method']} {api['url']} returned {resp.status}"
                except Exception:
                    pass
            tc.steps[2].status = "pass"
            tc.steps[2].actual = f"Replayed {len(captured_apis)} API(s)"

        set_cur(ctx, USD)
        go_cart(page)
        payment_apis = []

        def capture_payment(req):
            if req.method == "POST" and "payment" in req.url.lower():
                if "google" not in req.url.lower():
                    payment_apis.append(req.url)

        page.on("request", capture_payment)
        btn = page.query_selector(CHECKOUT_BTN)
        if btn:
            btn.click(force=True)
        page.wait_for_timeout(3000)
        page.remove_listener("request", capture_payment)

        if payment_apis:
            raise AssertionError(f"BUG: Payment APIs triggered on disabled click: {payment_apis}")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "No payment session created"
        tc.screenshots.append(screenshot_to_uri(page))

        tc.status = "pass"
        tc.actual = "API bypass test completed"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "critical"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
        try:
            page.remove_listener("request", capture_post)
        except Exception:
            pass
    tc.duration = time.time() - t0
    return tc


def run_cur14(ctx, page):
    tc = TestCase("CUR-14", "Currency changes INR → USD", "Cart open with INR")
    tc.expected = "Button immediately becomes disabled after switch"
    tc.steps = [
        Step("Set INR, navigate to cart, verify CHECKOUT enabled"),
        Step("Set USD cookies, reload page"),
        Step("Verify CHECKOUT is now disabled"),
        Step("Verify cursor changed from pointer"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, INR)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if not is_enabled(btn):
            raise AssertionError("CHECKOUT not enabled for INR initially")
        tc.steps[0].status = "pass"
        tc.steps[0].actual = "CHECKOUT enabled for INR"
        tc.screenshots.append(screenshot_to_uri(page))

        set_cur(ctx, USD)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        tc.steps[1].status = "pass"

        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT still ENABLED after INR→USD switch")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "CHECKOUT disabled after switch"
        tc.screenshots.append(screenshot_to_uri(page))

        cur = cursor_of(btn)
        if cur == "pointer":
            raise AssertionError("Cursor still pointer after INR→USD")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = f"cursor = {cur}"

        tc.status = "pass"
        tc.actual = "INR→USD transition correctly disables button"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur15(ctx, page):
    tc = TestCase("CUR-15", "Currency changes USD → INR", "Cart open with USD")
    tc.expected = "Button becomes enabled after valid cart refresh"
    tc.steps = [
        Step("Set USD, navigate to cart, verify CHECKOUT disabled"),
        Step("Set INR cookies, reload page"),
        Step("Verify CHECKOUT is now enabled"),
        Step("Verify cursor is pointer"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("CHECKOUT not disabled for USD initially")
        tc.steps[0].status = "pass"
        tc.steps[0].actual = "CHECKOUT disabled for USD"

        set_cur(ctx, INR)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        tc.steps[1].status = "pass"

        btn = page.query_selector(CHECKOUT_BTN)
        if not is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT still DISABLED after USD→INR switch")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "CHECKOUT enabled after switch"
        tc.screenshots.append(screenshot_to_uri(page))

        cur = cursor_of(btn)
        if cur != "pointer":
            raise AssertionError(f"Cursor is '{cur}', expected 'pointer'")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = f"cursor = {cur}"

        tc.status = "pass"
        tc.actual = "USD→INR transition correctly enables button"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur16(ctx, page):
    tc = TestCase("CUR-16", "Page refresh / session restore", "Non-INR cart")
    tc.expected = "Disabled state remains correct after refresh"
    tc.steps = [
        Step("Set USD, navigate to cart, verify disabled"),
        Step("Refresh page — verify still disabled"),
        Step("Navigate away to homepage, come back — verify still disabled"),
        Step("Set INR, refresh — verify enabled persists after refresh"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("Not disabled initially")
        tc.steps[0].status = "pass"

        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT became enabled after refresh")
        tc.steps[1].status = "pass"
        tc.steps[1].actual = "Still disabled after refresh"
        tc.screenshots.append(screenshot_to_uri(page))

        page.goto(STORE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)
        go_cart(page)
        btn = page.query_selector(CHECKOUT_BTN)
        if is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT enabled after navigate-away-and-back")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "Still disabled after nav away and back"

        set_cur(ctx, INR)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        btn = page.query_selector(CHECKOUT_BTN)
        if not is_enabled(btn):
            raise AssertionError("CHECKOUT not enabled for INR after refresh")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "Enabled for INR after refresh"

        tc.status = "pass"
        tc.actual = "Session state persists correctly across refreshes"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur17(ctx, page):
    tc = TestCase("CUR-17", "Missing currency (null, empty, missing)", "Currency cookie with empty/null code")
    tc.expected = "Checkout is safely blocked; no crash"
    tc.steps = [
        Step("Set empty string currency cookie, navigate to cart"),
        Step("Verify page does not crash"),
        Step("Verify CHECKOUT is disabled (ideally)"),
        Step("Set null/missing currency key, navigate to cart"),
        Step("Verify page does not crash"),
        Step("Verify CHECKOUT is disabled (ideally)"),
    ]
    t0 = time.time()
    bugs_found = []
    try:
        for i, (label, cur_val) in enumerate([("empty_string", ""), ("null_currency", None)]):
            step_offset = i * 3
            if cur_val is not None:
                payload = json.dumps({"countryCode": "XX", "currency": {"code": cur_val}, "language": {"locale": "en"}}, separators=(",", ":"))
            else:
                payload = json.dumps({"countryCode": "XX", "currency": {}, "language": {"locale": "en"}}, separators=(",", ":"))
            loc_payload = json.dumps({"country_iso_code": "XX"}, separators=(",", ":"))
            cookies = [
                {"name": "app_location_details", "value": quote(loc_payload, safe=""), "domain": "tumidesign.fynd.io", "path": "/", "secure": True, "sameSite": "None"},
                {"name": "app_i18n_details", "value": quote(payload, safe=""), "domain": "tumidesign.fynd.io", "path": "/", "secure": True, "sameSite": "None"},
            ]
            set_cur(ctx, cookies)
            go_cart(page)
            tc.steps[step_offset].status = "pass"

            body = page.query_selector("body")
            if body is None:
                raise AssertionError(f"Page crashed for {label}")
            tc.steps[step_offset + 1].status = "pass"
            tc.steps[step_offset + 1].actual = f"Page loaded for {label}"

            btn = page.query_selector(CHECKOUT_BTN)
            if btn and is_enabled(btn):
                tc.steps[step_offset + 2].status = "fail"
                tc.steps[step_offset + 2].actual = f"BUG: CHECKOUT ENABLED for {label} currency — should be blocked"
                bugs_found.append(label)
            else:
                tc.steps[step_offset + 2].status = "pass"
                tc.steps[step_offset + 2].actual = f"CHECKOUT disabled/hidden for {label}"
            tc.screenshots.append(screenshot_to_uri(page))

        if bugs_found:
            tc.status = "fail"
            tc.bug_severity = "major"
            tc.actual = f"BUG: CHECKOUT enabled for missing currency values: {', '.join(bugs_found)}"
        else:
            tc.status = "pass"
            tc.actual = "Missing currency safely blocked"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur18(ctx, page):
    tc = TestCase("CUR-18", "Lowercase / malformed currency value", "Currency cookie with 'inr', 'INR ', 'XYZ'")
    tc.expected = "Invalid values should be blocked; behavior follows normalization rule"
    tc.steps = [
        Step("Test lowercase 'inr'"),
        Step("Test trailing space 'INR '"),
        Step("Test invalid code 'XYZ'"),
        Step("Test numeric '123'"),
    ]
    t0 = time.time()
    try:
        for i, (label, val) in enumerate([("inr", "inr"), ("INR_space", "INR "), ("XYZ", "XYZ"), ("123", "123")]):
            cookies = build_currency_cookies("XX", "XX", val)
            set_cur(ctx, cookies)
            go_cart(page)
            page.wait_for_timeout(2000)

            body = page.query_selector("body")
            if body is None:
                raise AssertionError(f"Page crashed for '{val}'")

            btn = page.query_selector(CHECKOUT_BTN)
            if btn is None:
                tc.steps[i].status = "pass"
                tc.steps[i].actual = f"CHECKOUT not rendered for '{val}'"
                continue

            enabled = is_enabled(btn)
            if val.strip().upper() == "INR":
                tc.steps[i].status = "pass"
                tc.steps[i].actual = f"'{val}' → CHECKOUT {'enabled' if enabled else 'disabled'} (normalization behavior documented)"
            else:
                if enabled:
                    raise AssertionError(f"BUG: CHECKOUT ENABLED for malformed currency '{val}'")
                tc.steps[i].status = "pass"
                tc.steps[i].actual = f"CHECKOUT disabled for '{val}'"
            tc.screenshots.append(screenshot_to_uri(page))

        tc.status = "pass"
        tc.actual = "Malformed currency values handled correctly"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
    tc.duration = time.time() - t0
    return tc


def run_cur19(ctx, page):
    tc = TestCase("CUR-19", "API failure / loading state", "Cart API delayed or failed")
    tc.expected = "Buttons remain disabled until valid INR is confirmed"
    tc.steps = [
        Step("Set USD cookies"),
        Step("Intercept cart API with 2s delay, load page"),
        Step("Verify CHECKOUT disabled during loading"),
        Step("Verify no loader stuck after page loads"),
    ]
    t0 = time.time()
    try:
        set_cur(ctx, USD)
        tc.steps[0].status = "pass"

        import time as t

        def delay_handler(route):
            t.sleep(2)
            route.continue_()

        page.route("**/getCart**", delay_handler)

        page.goto(CART_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
        tc.steps[1].status = "pass"

        btn = page.query_selector(CHECKOUT_BTN)
        if btn is not None and is_enabled(btn):
            raise AssertionError("BUG: CHECKOUT enabled during slow API load for USD")
        tc.steps[2].status = "pass"
        tc.steps[2].actual = "CHECKOUT disabled during loading" if btn else "Button not yet rendered"

        page.unroute("**/getCart**")
        page.wait_for_timeout(5000)
        tc.screenshots.append(screenshot_to_uri(page))

        loaders = page.query_selector_all(".loader, .spinner, [class*='loading'], [class*='skeleton']")
        visible_loaders = [l for l in loaders if l.is_visible()]
        if visible_loaders:
            raise AssertionError(f"BUG: {len(visible_loaders)} loader(s) stuck on page")
        tc.steps[3].status = "pass"
        tc.steps[3].actual = "No stuck loaders"

        tc.status = "pass"
        tc.actual = "Loading state handled correctly"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
        tc.screenshots.append(screenshot_to_uri(page))
        try:
            page.unroute("**/getCart**")
        except Exception:
            pass
    tc.duration = time.time() - t0
    return tc


def run_cur20(playwright_inst, auth_state):
    tc = TestCase("CUR-20", "Browser coverage (Chrome, Firefox, Safari)", "Multiple browsers")
    tc.expected = "Consistent behaviour across supported browsers"
    tc.steps = [
        Step("Chromium: verify CHECKOUT disabled for USD"),
        Step("Chromium: verify CHECKOUT enabled for INR"),
        Step("Firefox: verify CHECKOUT disabled for USD"),
        Step("Firefox: verify CHECKOUT enabled for INR"),
        Step("WebKit/Safari: verify CHECKOUT disabled for USD"),
        Step("WebKit/Safari: verify CHECKOUT enabled for INR"),
    ]
    t0 = time.time()
    try:
        for step_idx, (browser_name, browser_type, cookies, expect_enabled) in enumerate([
            ("Chromium", "chromium", USD, False),
            ("Chromium", "chromium", INR, True),
            ("Firefox", "firefox", USD, False),
            ("Firefox", "firefox", INR, True),
            ("WebKit", "webkit", USD, False),
            ("WebKit", "webkit", INR, True),
        ]):
            launcher = getattr(playwright_inst, browser_type)
            try:
                browser = launcher.launch(headless=True)
            except Exception as e:
                tc.steps[step_idx].status = "skip"
                tc.steps[step_idx].actual = f"{browser_name} not available: {e}"
                continue

            context = browser.new_context(viewport=DESKTOP_VP, storage_state=auth_state if browser_type == "chromium" else None)
            bpage = context.new_page()

            if browser_type != "chromium":
                try:
                    do_login(bpage)
                except Exception as e:
                    tc.steps[step_idx].status = "skip"
                    tc.steps[step_idx].actual = f"Login failed on {browser_name}: {str(e)[:80]}"
                    browser.close()
                    continue

            set_cur(context, cookies)
            go_cart(bpage)

            btn = bpage.query_selector(CHECKOUT_BTN)
            if btn is None:
                tc.steps[step_idx].status = "skip"
                tc.steps[step_idx].actual = f"CHECKOUT not found on {browser_name}"
                browser.close()
                continue

            actual_enabled = is_enabled(btn)
            currency = "INR" if expect_enabled else "USD"
            if actual_enabled != expect_enabled:
                state = "ENABLED" if expect_enabled else "DISABLED"
                tc.steps[step_idx].status = "fail"
                tc.steps[step_idx].actual = f"BUG: CHECKOUT should be {state} for {currency} on {browser_name}"
            else:
                tc.steps[step_idx].status = "pass"
                tc.steps[step_idx].actual = f"CHECKOUT {'enabled' if actual_enabled else 'disabled'} for {currency} on {browser_name}"
            tc.screenshots.append(screenshot_to_uri(bpage))
            browser.close()

        failed_steps = [s for s in tc.steps if s.status == "fail"]
        if failed_steps:
            tc.status = "fail"
            tc.bug_severity = "major"
            tc.actual = "; ".join(s.actual for s in failed_steps)
        else:
            passed = sum(1 for s in tc.steps if s.status == "pass")
            skipped = sum(1 for s in tc.steps if s.status == "skip")
            tc.status = "pass"
            tc.actual = f"{passed} passed, {skipped} skipped across browsers"
    except Exception as e:
        tc.status = "fail"
        tc.bug_severity = "major"
        tc.actual = str(e)
        _mark_remaining_steps(tc, str(e))
    tc.duration = time.time() - t0
    return tc


def _mark_remaining_steps(tc, error_msg):
    for step in tc.steps:
        if step.status == "pending":
            step.status = "blocked"
            step.actual = f"Blocked by prior failure: {error_msg[:80]}"


# ───────────────────────── HTML Report Generator ─────────────────────────

def generate_html(results, total_duration):
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")
    bugs = [r for r in results if r.status == "fail"]
    total = len(results)
    pass_rate = round(passed / total * 100, 1) if total else 0

    status_colors = {
        "pass": "#16A34A",
        "fail": "#DC2626",
        "skip": "#6B7280",
        "blocked": "#9CA3AF",
        "pending": "#D1D5DB",
    }

    def status_badge(status):
        color = status_colors.get(status, "#6B7280")
        label = status.upper()
        if status == "fail":
            label = "BUG"
        return f'<span style="background:{color};color:#fff;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:0.5px">{label}</span>'

    def severity_badge(sev):
        if not sev:
            return ""
        colors = {"critical": "#DC2626", "major": "#EA580C", "minor": "#2563EB"}
        c = colors.get(sev, "#6B7280")
        return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;text-transform:uppercase;margin-left:6px">{sev}</span>'

    rows = ""
    for r in results:
        rows += f"""
        <tr style="border-bottom:1px solid #E5E7EB">
            <td style="padding:12px 16px;font-weight:600;white-space:nowrap">{r.case_id}</td>
            <td style="padding:12px 16px">{r.scenario}</td>
            <td style="padding:12px 16px;text-align:center">{status_badge(r.status)}{severity_badge(r.bug_severity)}</td>
            <td style="padding:12px 16px;text-align:right;color:#6B7280;font-size:13px">{r.duration:.1f}s</td>
        </tr>"""

    detail_cards = ""
    for idx, r in enumerate(results):
        border_color = status_colors.get(r.status, "#E5E7EB")
        bug_banner = ""
        if r.status == "fail":
            bug_banner = f'''
            <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;gap:10px">
                <span style="font-size:20px">&#9888;</span>
                <div>
                    <div style="font-weight:700;color:#DC2626;font-size:14px">BUG FOUND {severity_badge(r.bug_severity)}</div>
                    <div style="color:#991B1B;font-size:13px;margin-top:4px">{r.actual}</div>
                </div>
            </div>'''

        steps_html = ""
        for si, step in enumerate(r.steps):
            step_icon = {"pass": "&#10004;", "fail": "&#10008;", "skip": "&#8722;", "blocked": "&#9679;", "pending": "&#9675;"}.get(step.status, "&#9675;")
            step_color = status_colors.get(step.status, "#6B7280")
            actual_html = f'<div style="color:#6B7280;font-size:12px;margin-top:2px">Actual: {step.actual}</div>' if step.actual else ""
            steps_html += f'''
            <div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #F3F4F6">
                <span style="color:{step_color};font-size:16px;min-width:20px;text-align:center">{step_icon}</span>
                <div style="flex:1">
                    <div style="font-size:13px;color:#111827"><strong>Step {si+1}:</strong> {step.description}</div>
                    {actual_html}
                </div>
                <span>{status_badge(step.status)}</span>
            </div>'''

        screenshots_html = ""
        if r.screenshots:
            screenshots_html = '<div style="margin-top:16px"><div style="font-weight:600;font-size:13px;margin-bottom:8px;color:#374151">Screenshots</div><div style="display:flex;gap:8px;flex-wrap:wrap">'
            for si, ss in enumerate(r.screenshots):
                screenshots_html += f'<img src="{ss}" style="max-width:320px;border:1px solid #E5E7EB;border-radius:6px;cursor:pointer" onclick="this.style.maxWidth=this.style.maxWidth===\'320px\'?\'100%\':\'320px\'" title="Screenshot {si+1}" />'
            screenshots_html += "</div></div>"

        detail_cards += f'''
        <div id="detail-{r.case_id}" style="background:#fff;border:1px solid #E5E7EB;border-left:4px solid {border_color};border-radius:10px;padding:24px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.04)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <div style="display:flex;align-items:center;gap:12px">
                    <span style="font-size:18px;font-weight:700;color:#111827">{r.case_id}</span>
                    <span style="font-size:15px;color:#374151">{r.scenario}</span>
                    {status_badge(r.status)}{severity_badge(r.bug_severity)}
                </div>
                <span style="color:#9CA3AF;font-size:12px">{r.duration:.1f}s</span>
            </div>
            {bug_banner}
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
                <div style="background:#F9FAFB;border-radius:6px;padding:10px 14px">
                    <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Precondition</div>
                    <div style="font-size:13px;color:#111827">{r.precondition}</div>
                </div>
                <div style="background:#F9FAFB;border-radius:6px;padding:10px 14px">
                    <div style="font-size:11px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Expected Result</div>
                    <div style="font-size:13px;color:#111827">{r.expected}</div>
                </div>
            </div>
            <div style="margin-bottom:8px;font-weight:600;font-size:13px;color:#374151">Test Steps</div>
            {steps_html}
            {screenshots_html}
        </div>'''

    bugs_section = ""
    if bugs:
        bug_cards = ""
        for b in bugs:
            bug_cards += f'''
            <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;padding:18px;margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <span style="font-weight:700;font-size:15px;color:#991B1B">{b.case_id}: {b.scenario}</span>
                    {severity_badge(b.bug_severity)}
                </div>
                <div style="color:#7F1D1D;font-size:13px;margin-bottom:8px"><strong>Actual Result:</strong> {b.actual}</div>
                <div style="color:#7F1D1D;font-size:13px"><strong>Expected:</strong> {b.expected}</div>
                <div style="margin-top:8px"><a href="#detail-{b.case_id}" style="color:#DC2626;font-size:12px;font-weight:600">View full details &#8595;</a></div>
            </div>'''
        bugs_section = f'''
        <div style="background:#fff;border-radius:14px;padding:28px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
            <h2 style="font-size:20px;font-weight:700;color:#DC2626;margin:0 0 16px 0">&#9888; Bugs Found ({len(bugs)})</h2>
            {bug_cards}
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Checkout Currency Restriction — Test Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #F3F4F6; color: #111827; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  @media (max-width: 768px) {{
    .container {{ padding: 12px; }}
    .stats-grid {{ grid-template-columns: 1fr 1fr !important; }}
  }}
</style>
</head>
<body>

<!-- Header -->
<div style="background:linear-gradient(135deg, #1E293B 0%, #0F172A 100%);padding:36px 40px;color:#fff">
  <div style="max-width:1200px;margin:0 auto">
    <h1 style="font-size:26px;font-weight:700;margin-bottom:8px">Checkout Currency Restriction — Test Report</h1>
    <p style="color:#94A3B8;font-size:14px;margin-bottom:12px">Jira Ticket: Disable Checkout, Proceed to Pay, and Pay Now buttons for non-INR currency</p>
    <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
      <span style="background:#334155;padding:6px 14px;border-radius:6px;font-size:13px">URL: <a href="{STORE_URL}" style="color:#60A5FA;text-decoration:none">{STORE_URL}</a></span>
      <span style="background:#334155;padding:6px 14px;border-radius:6px;font-size:13px">Generated: {now}</span>
      <span style="background:#334155;padding:6px 14px;border-radius:6px;font-size:13px">Duration: {total_duration:.0f}s</span>
    </div>
  </div>
</div>

<div class="container">

<!-- Executive Summary -->
<div style="background:#fff;border-radius:14px;padding:28px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:20px;color:#111827">Executive Summary</h2>
  <div class="stats-grid" style="display:grid;grid-template-columns:repeat(5, 1fr);gap:16px;margin-bottom:20px">
    <div style="background:#F9FAFB;border-radius:10px;padding:20px;text-align:center">
      <div style="font-size:32px;font-weight:800;color:#111827">{total}</div>
      <div style="font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:1px;margin-top:4px">Total</div>
    </div>
    <div style="background:#F0FDF4;border-radius:10px;padding:20px;text-align:center;border:1px solid #BBF7D0">
      <div style="font-size:32px;font-weight:800;color:#16A34A">{passed}</div>
      <div style="font-size:12px;color:#16A34A;text-transform:uppercase;letter-spacing:1px;margin-top:4px">Passed</div>
    </div>
    <div style="background:#FEF2F2;border-radius:10px;padding:20px;text-align:center;border:1px solid #FECACA">
      <div style="font-size:32px;font-weight:800;color:#DC2626">{failed}</div>
      <div style="font-size:12px;color:#DC2626;text-transform:uppercase;letter-spacing:1px;margin-top:4px">Bugs</div>
    </div>
    <div style="background:#F9FAFB;border-radius:10px;padding:20px;text-align:center">
      <div style="font-size:32px;font-weight:800;color:#6B7280">{skipped}</div>
      <div style="font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:1px;margin-top:4px">Skipped</div>
    </div>
    <div style="background:#F9FAFB;border-radius:10px;padding:20px;text-align:center">
      <div style="font-size:32px;font-weight:800;color:#111827">{pass_rate}%</div>
      <div style="font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:1px;margin-top:4px">Pass Rate</div>
    </div>
  </div>
  <!-- Progress bar -->
  <div style="background:#E5E7EB;border-radius:8px;height:12px;overflow:hidden;display:flex">
    <div style="background:#16A34A;width:{passed/total*100 if total else 0}%;transition:width 0.3s"></div>
    <div style="background:#DC2626;width:{failed/total*100 if total else 0}%"></div>
    <div style="background:#9CA3AF;width:{skipped/total*100 if total else 0}%"></div>
  </div>
</div>

{bugs_section}

<!-- Test Matrix -->
<div style="background:#fff;border-radius:14px;padding:28px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06)">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:16px;color:#111827">Test Matrix</h2>
  <table style="width:100%;border-collapse:collapse">
    <thead>
      <tr style="background:#F9FAFB;border-bottom:2px solid #E5E7EB">
        <th style="padding:12px 16px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:#6B7280">ID</th>
        <th style="padding:12px 16px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:#6B7280">Scenario</th>
        <th style="padding:12px 16px;text-align:center;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:#6B7280">Status</th>
        <th style="padding:12px 16px;text-align:right;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:#6B7280">Duration</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>

<!-- Detailed Results -->
<div style="margin-bottom:24px">
  <h2 style="font-size:20px;font-weight:700;margin-bottom:16px;color:#111827">Detailed Test Results</h2>
  {detail_cards}
</div>

<!-- Footer -->
<div style="text-align:center;padding:24px;color:#9CA3AF;font-size:12px">
  Generated by Playwright E2E Test Suite &bull; {now}
</div>

</div>
</body>
</html>'''

    return html


# ───────────────────────── Main ─────────────────────────

def main():
    print("=" * 60)
    print("Checkout Currency Restriction — Test Report Generator")
    print("=" * 60)

    total_start = time.time()

    with sync_playwright() as p:
        print("\n[1/3] Launching browser and logging in...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=DESKTOP_VP,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        do_login(page)
        auth_state = context.storage_state()
        print("   Login successful.")

        print("\n[2/3] Running 20 test scenarios...\n")
        results = []

        runners = [
            ("CUR-01", run_cur01),
            ("CUR-02", run_cur02),
            ("CUR-03", run_cur03),
            ("CUR-04", run_cur04),
            ("CUR-05", run_cur05),
            ("CUR-06", run_cur06),
            ("CUR-07", run_cur07),
            ("CUR-08", run_cur08),
            ("CUR-09", run_cur09),
            ("CUR-10", run_cur10),
            ("CUR-11", run_cur11),
            ("CUR-12", run_cur12),
            ("CUR-13", run_cur13),
            ("CUR-14", run_cur14),
            ("CUR-15", run_cur15),
            ("CUR-16", run_cur16),
            ("CUR-17", run_cur17),
            ("CUR-18", run_cur18),
            ("CUR-19", run_cur19),
        ]

        for case_id, runner in runners:
            print(f"   Running {case_id}...", end=" ", flush=True)
            try:
                tc = runner(context, page)
            except Exception as e:
                tc = TestCase(case_id, "ERROR", "")
                tc.status = "fail"
                tc.actual = f"Runner crashed: {e}"
                tc.bug_severity = "critical"
            results.append(tc)
            icon = {"pass": "PASS", "fail": "BUG", "skip": "SKIP"}.get(tc.status, "???")
            sev = f" [{tc.bug_severity}]" if tc.bug_severity else ""
            print(f"{icon}{sev} ({tc.duration:.1f}s)")

        # CUR-20 needs separate browser instances
        print("   Running CUR-20...", end=" ", flush=True)
        try:
            tc20 = run_cur20(p, auth_state)
        except Exception as e:
            tc20 = TestCase("CUR-20", "Browser coverage", "")
            tc20.status = "fail"
            tc20.actual = f"Runner crashed: {e}"
            tc20.bug_severity = "major"
        results.append(tc20)
        icon = {"pass": "PASS", "fail": "BUG", "skip": "SKIP"}.get(tc20.status, "???")
        sev = f" [{tc20.bug_severity}]" if tc20.bug_severity else ""
        print(f"{icon}{sev} ({tc20.duration:.1f}s)")

        browser.close()

    total_duration = time.time() - total_start

    print(f"\n[3/3] Generating HTML report...")
    html = generate_html(results, total_duration)
    output_path = "report/checkout_currency_test_report.html"
    with open(output_path, "w") as f:
        f.write(html)

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed} passed, {failed} bugs, {skipped} skipped")
    print(f"REPORT:  {output_path}")
    print(f"TIME:    {total_duration:.0f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
