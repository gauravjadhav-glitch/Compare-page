"""Shared fixtures and helpers for checkout currency restriction E2E tests."""
import pytest
from urllib.parse import quote
import json
from playwright.sync_api import sync_playwright, Page, BrowserContext, Browser


STORE_URL = "https://tumidesign.fynd.io"
LOGIN_URL = f"{STORE_URL}/auth/login"
CART_URL = f"{STORE_URL}/cart/bag/"
CHECKOUT_URL = f"{STORE_URL}/cart/checkout"
MOBILE_NUMBER = "8888888888"
OTP = "5401"

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
IPHONE_VIEWPORT = {"width": 375, "height": 812}
ANDROID_VIEWPORT = {"width": 360, "height": 640}

CHECKOUT_BTN_DESKTOP = "button.Emf2f:has-text('CHECKOUT')"
CHECKOUT_BTN_STICKY = (
    "button.sticky-footer__cartCheckoutBtn___Mw2z8:has-text('CHECKOUT')"
)
PROCEED_BTN_DESKTOP = "button.single-shipment-content__proceedBtn___csoKN"
PROCEED_BTN_STICKY = "button.sticky-pay-now__cartCheckoutBtn___jwQXW"

CHECKOUT_KEYWORDS = ["Checkout", "CHECKOUT"]
PROCEED_KEYWORDS = ["Proceed", "PROCEED TO PAY"]
PAY_KEYWORDS = ["Pay Now", "PAY NOW", "Pay"]


def build_i18n_cookie(country_code, currency_code):
    payload = json.dumps({
        "countryCode": country_code,
        "currency": {"code": currency_code},
        "language": {"locale": "en"},
    }, separators=(",", ":"))
    return quote(payload, safe="")


def build_location_cookie(country_iso):
    payload = json.dumps(
        {"country_iso_code": country_iso},
        separators=(",", ":"),
    )
    return quote(payload, safe="")


def make_currency_cookies(country_iso, country_code, currency_code):
    return [
        {
            "name": "app_location_details",
            "value": build_location_cookie(country_iso),
            "domain": "tumidesign.fynd.io",
            "path": "/",
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "app_i18n_details",
            "value": build_i18n_cookie(country_code, currency_code),
            "domain": "tumidesign.fynd.io",
            "path": "/",
            "secure": True,
            "sameSite": "None",
        },
    ]


INR_COOKIES = make_currency_cookies("IN", "IN", "INR")
USD_COOKIES = make_currency_cookies("US", "US", "USD")
EUR_COOKIES = make_currency_cookies("DE", "DE", "EUR")
AED_COOKIES = make_currency_cookies("AE", "AE", "AED")
GBP_COOKIES = make_currency_cookies("GB", "GB", "GBP")


def login(page: Page):
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    page.wait_for_selector("input[name='phone']", timeout=15000)
    page.fill("input[name='phone']", MOBILE_NUMBER)

    checkbox = page.query_selector("input[type='checkbox']")
    if checkbox and not checkbox.is_checked():
        checkbox.check(force=True)

    page.wait_for_timeout(500)
    page.click("button:has-text('GET OTP')")
    page.wait_for_selector("input[name='mobileOtp']", timeout=10000)
    page.fill("input[name='mobileOtp']", OTP)
    page.click("button:has-text('CONTINUE')")
    page.wait_for_timeout(5000)


def set_currency(context: BrowserContext, cookies: list):
    context.add_cookies(cookies)


def navigate_to_cart(page: Page):
    page.goto(CART_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)


def navigate_to_checkout_via_button(page: Page):
    checkout_btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
    if checkout_btn and is_button_enabled(checkout_btn):
        checkout_btn.click()
        page.wait_for_timeout(5000)


def is_button_enabled(button) -> bool:
    return button.get_attribute("disabled") is None


def get_visible_buttons(page: Page, text: str) -> list:
    buttons = page.query_selector_all(f"button:has-text('{text}')")
    return [btn for btn in buttons if btn.is_visible()]


def get_button_cursor(button) -> str:
    return button.evaluate("el => getComputedStyle(el).cursor")


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance):
    b = playwright_instance.chromium.launch(headless=True)
    yield b
    b.close()


@pytest.fixture(scope="session")
def auth_storage_state(browser):
    context = browser.new_context(
        viewport=DESKTOP_VIEWPORT,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    login(page)
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture()
def logged_in_context(browser, auth_storage_state):
    context = browser.new_context(
        viewport=DESKTOP_VIEWPORT,
        storage_state=auth_storage_state,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    yield context
    context.close()


@pytest.fixture()
def page(logged_in_context):
    p = logged_in_context.new_page()
    yield p
    p.close()


@pytest.fixture()
def api_request_log(page):
    captured = []

    def on_request(request):
        url = request.url.lower()
        is_platform_api = (
            "api.fynd.com" in url
            or "fyndx1" in url
            or "/ext/" in url
        )
        is_cart_checkout = any(
            kw in url
            for kw in ["cart", "checkout", "payment", "order", "shipment"]
        )
        if is_platform_api or is_cart_checkout:
            if "google" not in url and "analytics" not in url and "bing" not in url:
                captured.append({
                    "method": request.method,
                    "url": request.url,
                    "post_data": request.post_data,
                })

    page.on("request", on_request)
    yield captured
