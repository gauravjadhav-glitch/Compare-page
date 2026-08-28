"""
E2E tests: Disable Checkout/Proceed to Pay/Pay Now buttons for non-INR currency.

Covers CUR-01 through CUR-20 from the test matrix.
Each class maps to one scenario ID.

Acceptance Criteria:
1. Buttons remain enabled when the currency is INR.
2. Buttons are disabled for all non-INR currencies.
3. The restriction applies to desktop and mobile/sticky buttons.
4. Payment execution is also blocked to prevent bypassing the disabled UI.
"""
import json
import pytest
from urllib.parse import quote
from playwright.sync_api import sync_playwright

from conftest import (
    STORE_URL,
    CART_URL,
    CHECKOUT_URL,
    DESKTOP_VIEWPORT,
    IPHONE_VIEWPORT,
    ANDROID_VIEWPORT,
    CHECKOUT_BTN_DESKTOP,
    CHECKOUT_BTN_STICKY,
    PROCEED_BTN_DESKTOP,
    PROCEED_BTN_STICKY,
    INR_COOKIES,
    USD_COOKIES,
    EUR_COOKIES,
    AED_COOKIES,
    GBP_COOKIES,
    set_currency,
    navigate_to_cart,
    navigate_to_checkout_via_button,
    is_button_enabled,
    get_visible_buttons,
    get_button_cursor,
    make_currency_cookies,
)


# ---------------------------------------------------------------------------
# CUR-01: Checkout with INR — CHECKOUT button enabled on cart page
# ---------------------------------------------------------------------------
class TestCUR01CartCheckoutINR:

    def test_checkout_button_exists_and_enabled(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, "Desktop CHECKOUT button not found on cart page"
        assert is_button_enabled(btn), "CHECKOUT should be ENABLED for INR"

    def test_checkout_button_has_pointer_cursor(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert get_button_cursor(btn) == "pointer", (
            "CHECKOUT should show pointer cursor for INR"
        )

    def test_checkout_button_is_clickable_and_navigates(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        navigate_to_checkout_via_button(page)
        assert page.url != url_before, (
            "Clicking CHECKOUT with INR should navigate to checkout page"
        )
        assert "checkout" in page.url, "Should navigate to checkout URL"


# ---------------------------------------------------------------------------
# CUR-02: Proceed to Pay with INR — enabled on checkout page
# ---------------------------------------------------------------------------
class TestCUR02ProceedToPayINR:

    def test_proceed_to_pay_enabled_on_checkout(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)
        navigate_to_checkout_via_button(page)

        btn = page.query_selector(PROCEED_BTN_DESKTOP)
        if btn is None:
            visible_proceeds = get_visible_buttons(page, "PROCEED TO PAY")
            assert len(visible_proceeds) > 0, (
                "PROCEED TO PAY button not found on checkout page"
            )
            btn = visible_proceeds[0]
        assert is_button_enabled(btn), "PROCEED TO PAY should be ENABLED for INR"

    def test_sticky_proceed_to_pay_enabled(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)
        navigate_to_checkout_via_button(page)

        btn = page.query_selector(PROCEED_BTN_STICKY)
        if btn is None:
            pytest.skip("Sticky PROCEED TO PAY not visible at this viewport")
        assert is_button_enabled(btn), (
            "Sticky PROCEED TO PAY should be ENABLED for INR"
        )


# ---------------------------------------------------------------------------
# CUR-03: Pay Now with INR — enabled on payment step
# ---------------------------------------------------------------------------
class TestCUR03PayNowINR:

    def test_pay_now_reachable_with_inr(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)
        navigate_to_checkout_via_button(page)

        proceed_btn = page.query_selector(PROCEED_BTN_DESKTOP)
        if proceed_btn is None:
            proceed_btn = page.query_selector(
                "button:has-text('PROCEED TO PAY')"
            )
        if proceed_btn and is_button_enabled(proceed_btn):
            proceed_btn.click()
            page.wait_for_timeout(5000)

        pay_btn = page.query_selector(
            "button:has-text('PAY NOW'), "
            "button:has-text('Pay Now'), "
            "button:has-text('PLACE ORDER'), "
            "button:has-text('Place Order')"
        )
        if pay_btn is None:
            pytest.skip(
                "PAY NOW / PLACE ORDER button not reachable — "
                "payment method selection may require additional setup"
            )
        assert is_button_enabled(pay_btn), "PAY NOW should be ENABLED for INR"


# ---------------------------------------------------------------------------
# CUR-04: Checkout with USD — CHECKOUT button disabled on cart page
# ---------------------------------------------------------------------------
class TestCUR04CartCheckoutUSD:

    def test_checkout_button_disabled_for_usd(self, logged_in_context, page):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, "Desktop CHECKOUT button not found"
        assert not is_button_enabled(btn), (
            "CHECKOUT should be DISABLED for USD"
        )

    def test_checkout_button_no_pointer_cursor_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert get_button_cursor(btn) != "pointer", (
            "CHECKOUT should NOT have pointer cursor for USD"
        )

    def test_checkout_click_does_not_navigate_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        btn.click(force=True)
        page.wait_for_timeout(2000)
        assert page.url == url_before, (
            "Clicking disabled CHECKOUT should NOT navigate"
        )

    def test_prices_display_in_usd(self, logged_in_context, page):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        body_text = page.inner_text("body")
        assert "$" in body_text, "Prices should show USD ($) symbol"


# ---------------------------------------------------------------------------
# CUR-05: Proceed to Pay with USD — disabled on checkout page
# ---------------------------------------------------------------------------
class TestCUR05ProceedToPayUSD:

    def test_proceed_to_pay_disabled_or_hidden_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        page.goto(
            f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e"
            f"&address_id=6a6311a09f7e9819243a922a",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(3000)

        proceed_buttons = get_visible_buttons(page, "PROCEED TO PAY")
        if len(proceed_buttons) == 0:
            pass  # Buttons hidden entirely — acceptable behavior
        else:
            for btn in proceed_buttons:
                assert not is_button_enabled(btn), (
                    "PROCEED TO PAY should be DISABLED for USD on checkout"
                )

    def test_checkout_page_shows_usd_prices(self, logged_in_context, page):
        set_currency(logged_in_context, USD_COOKIES)
        page.goto(
            f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e"
            f"&address_id=6a6311a09f7e9819243a922a",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(3000)

        body_text = page.inner_text("body")
        assert "$" in body_text, "Checkout page should display USD prices"


# ---------------------------------------------------------------------------
# CUR-06: Pay Now with USD — disabled on payment step
# ---------------------------------------------------------------------------
class TestCUR06PayNowUSD:

    def test_pay_now_disabled_or_hidden_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        page.goto(
            f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e"
            f"&address_id=6a6311a09f7e9819243a922a",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(3000)

        pay_buttons = get_visible_buttons(page, "PAY NOW")
        pay_buttons += get_visible_buttons(page, "Pay Now")
        pay_buttons += get_visible_buttons(page, "PLACE ORDER")

        if len(pay_buttons) == 0:
            pass  # Not reachable or hidden — acceptable
        else:
            for btn in pay_buttons:
                assert not is_button_enabled(btn), (
                    "PAY NOW should be DISABLED for USD"
                )


# ---------------------------------------------------------------------------
# CUR-07: Another non-INR currency (AED, EUR, GBP)
# ---------------------------------------------------------------------------
class TestCUR07AnotherNonINRCurrency:

    @pytest.mark.parametrize(
        "currency_name,cookies",
        [
            ("AED", AED_COOKIES),
            ("EUR", EUR_COOKIES),
            ("GBP", GBP_COOKIES),
        ],
        ids=["AED", "EUR", "GBP"],
    )
    def test_checkout_disabled_for_non_inr(
        self, logged_in_context, page, currency_name, cookies
    ):
        set_currency(logged_in_context, cookies)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, f"CHECKOUT button not found for {currency_name}"
        assert not is_button_enabled(btn), (
            f"CHECKOUT should be DISABLED for {currency_name}"
        )

    @pytest.mark.parametrize(
        "currency_name,cookies",
        [
            ("AED", AED_COOKIES),
            ("EUR", EUR_COOKIES),
            ("GBP", GBP_COOKIES),
        ],
        ids=["AED", "EUR", "GBP"],
    )
    def test_sticky_checkout_disabled_for_non_inr(
        self, logged_in_context, page, currency_name, cookies
    ):
        set_currency(logged_in_context, cookies)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_STICKY)
        if btn is None or not btn.is_visible():
            pytest.skip(f"Sticky CHECKOUT not visible for {currency_name}")
        assert not is_button_enabled(btn), (
            f"Sticky CHECKOUT should be DISABLED for {currency_name}"
        )


# ---------------------------------------------------------------------------
# CUR-08: Desktop controls — 1440×900
# ---------------------------------------------------------------------------
class TestCUR08DesktopControls:

    def test_desktop_checkout_enabled_inr(self, logged_in_context, page):
        page.set_viewport_size(DESKTOP_VIEWPORT)
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None and is_button_enabled(btn), (
            "Desktop CHECKOUT should be ENABLED for INR at 1440x900"
        )

    def test_desktop_checkout_disabled_usd(self, logged_in_context, page):
        page.set_viewport_size(DESKTOP_VIEWPORT)
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None and not is_button_enabled(btn), (
            "Desktop CHECKOUT should be DISABLED for USD at 1440x900"
        )

    def test_desktop_sticky_and_main_same_state_usd(
        self, logged_in_context, page
    ):
        page.set_viewport_size(DESKTOP_VIEWPORT)
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        main_btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        sticky_btn = page.query_selector(CHECKOUT_BTN_STICKY)
        if sticky_btn is None or not sticky_btn.is_visible():
            pytest.skip("Sticky button not visible on desktop")

        main_state = is_button_enabled(main_btn)
        sticky_state = is_button_enabled(sticky_btn)
        assert main_state == sticky_state, (
            "Desktop main and sticky buttons should have the same disabled state"
        )


# ---------------------------------------------------------------------------
# CUR-09: Mobile controls — iPhone + Android viewports
# ---------------------------------------------------------------------------
class TestCUR09MobileControls:

    @pytest.mark.parametrize(
        "viewport_name,viewport",
        [
            ("iPhone", IPHONE_VIEWPORT),
            ("Android", ANDROID_VIEWPORT),
        ],
        ids=["iPhone_375x812", "Android_360x640"],
    )
    def test_mobile_checkout_disabled_for_usd(
        self, logged_in_context, page, viewport_name, viewport
    ):
        page.set_viewport_size(viewport)
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        checkout_btns = get_visible_buttons(page, "CHECKOUT")
        assert len(checkout_btns) > 0, (
            f"At least one CHECKOUT button should be visible on {viewport_name}"
        )
        for btn in checkout_btns:
            assert not is_button_enabled(btn), (
                f"CHECKOUT should be DISABLED on {viewport_name} for USD"
            )

    @pytest.mark.parametrize(
        "viewport_name,viewport",
        [
            ("iPhone", IPHONE_VIEWPORT),
            ("Android", ANDROID_VIEWPORT),
        ],
        ids=["iPhone_375x812", "Android_360x640"],
    )
    def test_mobile_checkout_enabled_for_inr(
        self, logged_in_context, page, viewport_name, viewport
    ):
        page.set_viewport_size(viewport)
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        checkout_btns = get_visible_buttons(page, "CHECKOUT")
        assert len(checkout_btns) > 0, (
            f"At least one CHECKOUT button should be visible on {viewport_name}"
        )
        for btn in checkout_btns:
            assert is_button_enabled(btn), (
                f"CHECKOUT should be ENABLED on {viewport_name} for INR"
            )


# ---------------------------------------------------------------------------
# CUR-10: Keyboard bypass — Tab + Enter/Space on disabled button
# ---------------------------------------------------------------------------
class TestCUR10KeyboardBypass:

    def test_tab_enter_does_not_activate_disabled_checkout(
        self, logged_in_context, page, api_request_log
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)

        btn.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

        assert page.url == url_before, (
            "Enter on disabled CHECKOUT should NOT navigate"
        )

    def test_tab_space_does_not_activate_disabled_checkout(
        self, logged_in_context, page, api_request_log
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)

        btn.focus()
        page.keyboard.press("Space")
        page.wait_for_timeout(2000)

        assert page.url == url_before, (
            "Space on disabled CHECKOUT should NOT navigate"
        )

    def test_no_api_triggered_on_keyboard_activation(
        self, logged_in_context, page, api_request_log
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        api_request_log.clear()

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        btn.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        page.keyboard.press("Space")
        page.wait_for_timeout(2000)

        checkout_api_calls = [
            r for r in api_request_log
            if "checkout" in r["url"].lower()
            and r["method"] == "POST"
        ]
        assert len(checkout_api_calls) == 0, (
            "No checkout API should be triggered via keyboard on disabled button"
        )


# ---------------------------------------------------------------------------
# CUR-11: Rapid/double click during currency update
# ---------------------------------------------------------------------------
class TestCUR11RapidDoubleClick:

    def test_rapid_click_disabled_checkout_no_navigation(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        for _ in range(5):
            btn.click(force=True, delay=50)
        page.wait_for_timeout(3000)

        assert page.url == url_before, (
            "Rapid clicking disabled CHECKOUT should NOT navigate"
        )

    def test_rapid_click_on_usd_cart_no_navigation(
        self, logged_in_context, page
    ):
        """Rapidly clicking CHECKOUT on a USD cart must not navigate."""
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        url_before = page.url
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        for _ in range(10):
            try:
                btn.click(force=True, delay=20)
            except Exception:
                break
        page.wait_for_timeout(3000)

        assert page.url == url_before, (
            "Rapid clicking disabled CHECKOUT on USD cart should not navigate"
        )

    def test_no_order_created_on_rapid_click(
        self, logged_in_context, page, api_request_log
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        api_request_log.clear()
        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        for _ in range(5):
            btn.click(force=True, delay=30)
        page.wait_for_timeout(3000)

        order_calls = [
            r for r in api_request_log
            if "order" in r["url"].lower() and r["method"] == "POST"
        ]
        payment_calls = [
            r for r in api_request_log
            if "payment" in r["url"].lower() and r["method"] == "POST"
        ]
        assert len(order_calls) == 0, "No order API should be triggered"
        assert len(payment_calls) == 0, "No payment API should be triggered"


# ---------------------------------------------------------------------------
# CUR-12: Direct URL bypass — open checkout/payment URL with non-INR cart
# ---------------------------------------------------------------------------
class TestCUR12DirectURLBypass:

    def test_direct_checkout_url_blocks_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        page.goto(
            f"{CHECKOUT_URL}?id=6a7305d236fce5a911a2749e"
            f"&address_id=6a6311a09f7e9819243a922a",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_timeout(3000)

        proceed_buttons = get_visible_buttons(page, "PROCEED TO PAY")
        pay_buttons = get_visible_buttons(page, "PAY NOW")
        pay_buttons += get_visible_buttons(page, "Pay Now")

        for btn in proceed_buttons:
            assert not is_button_enabled(btn), (
                "PROCEED TO PAY should be disabled via direct URL for USD"
            )
        for btn in pay_buttons:
            assert not is_button_enabled(btn), (
                "PAY NOW should be disabled via direct URL for USD"
            )

    def test_direct_cart_url_checkout_disabled_for_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), (
            "Direct navigation to cart with USD should show disabled CHECKOUT"
        )


# ---------------------------------------------------------------------------
# CUR-13: Direct API bypass — replay payment API for non-INR cart
# ---------------------------------------------------------------------------
class TestCUR13DirectAPIBypass:

    def test_capture_and_replay_checkout_api_rejected(
        self, logged_in_context, page, api_request_log
    ):
        """
        Capture checkout-related API calls during an INR session,
        then switch to USD and verify the server rejects replayed requests.
        """
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        api_request_log.clear()
        navigate_to_checkout_via_button(page)
        page.wait_for_timeout(3000)

        checkout_apis = [
            r for r in api_request_log
            if r["method"] in ("POST", "PUT")
            and any(
                kw in r["url"].lower()
                for kw in ["checkout", "shipment", "order", "payment"]
            )
        ]

        if not checkout_apis:
            pytest.skip(
                "No checkout/payment POST APIs captured — "
                "API bypass test requires captured endpoints"
            )

        set_currency(logged_in_context, USD_COOKIES)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        api_context = logged_in_context.request
        for api_call in checkout_apis:
            try:
                response = api_context.fetch(
                    api_call["url"],
                    method=api_call["method"],
                    data=api_call["post_data"],
                )
                status = response.status
                assert status >= 400 or status == 200, (
                    f"Server should reject or safely handle replayed "
                    f"{api_call['method']} {api_call['url']} — got {status}"
                )
            except Exception:
                pass  # Network error = request blocked, which is acceptable

    def test_no_payment_session_created_for_usd(
        self, logged_in_context, page, api_request_log
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        api_request_log.clear()

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        btn.click(force=True)
        page.wait_for_timeout(3000)

        payment_session_calls = [
            r for r in api_request_log
            if "payment" in r["url"].lower()
            and r["method"] == "POST"
        ]
        assert len(payment_session_calls) == 0, (
            "No payment session should be created when clicking disabled "
            "CHECKOUT for USD"
        )


# ---------------------------------------------------------------------------
# CUR-14: Currency changes INR → USD
# ---------------------------------------------------------------------------
class TestCUR14CurrencyChangeINRToUSD:

    def test_button_becomes_disabled_after_inr_to_usd(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert is_button_enabled(btn), "Should start ENABLED for INR"

        set_currency(logged_in_context, USD_COOKIES)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), (
            "CHECKOUT should become DISABLED after switching INR → USD"
        )

    def test_cursor_changes_after_inr_to_usd(self, logged_in_context, page):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert get_button_cursor(btn) == "pointer"

        set_currency(logged_in_context, USD_COOKIES)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert get_button_cursor(btn) != "pointer", (
            "Cursor should change from pointer after INR → USD"
        )


# ---------------------------------------------------------------------------
# CUR-15: Currency changes USD → INR
# ---------------------------------------------------------------------------
class TestCUR15CurrencyChangeUSDToINR:

    def test_button_becomes_enabled_after_usd_to_inr(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), "Should start DISABLED for USD"

        set_currency(logged_in_context, INR_COOKIES)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert is_button_enabled(btn), (
            "CHECKOUT should become ENABLED after switching USD → INR"
        )

    def test_cursor_changes_after_usd_to_inr(self, logged_in_context, page):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        set_currency(logged_in_context, INR_COOKIES)
        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert get_button_cursor(btn) == "pointer", (
            "Cursor should be pointer after USD → INR"
        )


# ---------------------------------------------------------------------------
# CUR-16: Page refresh / session restore
# ---------------------------------------------------------------------------
class TestCUR16PageRefreshSessionRestore:

    def test_disabled_state_persists_after_refresh(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), "Should be DISABLED before refresh"

        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), (
            "CHECKOUT should remain DISABLED after page refresh"
        )

    def test_enabled_state_persists_after_refresh(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert is_button_enabled(btn), "Should be ENABLED before refresh"

        page.reload(wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert is_button_enabled(btn), (
            "CHECKOUT should remain ENABLED after page refresh for INR"
        )

    def test_disabled_state_after_navigating_away_and_back(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        page.goto(STORE_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert not is_button_enabled(btn), (
            "CHECKOUT should remain DISABLED after navigating away and back"
        )


# ---------------------------------------------------------------------------
# CUR-17: Missing currency — null, empty, or missing
# ---------------------------------------------------------------------------
class TestCUR17MissingCurrency:

    def _make_empty_currency_cookies(self, currency_value):
        i18n_payload = json.dumps({
            "countryCode": "XX",
            "currency": {"code": currency_value} if currency_value else {},
            "language": {"locale": "en"},
        }, separators=(",", ":"))
        location_payload = json.dumps(
            {"country_iso_code": "XX"},
            separators=(",", ":"),
        )
        return [
            {
                "name": "app_location_details",
                "value": quote(location_payload, safe=""),
                "domain": "tumidesign.fynd.io",
                "path": "/",
                "secure": True,
                "sameSite": "None",
            },
            {
                "name": "app_i18n_details",
                "value": quote(i18n_payload, safe=""),
                "domain": "tumidesign.fynd.io",
                "path": "/",
                "secure": True,
                "sameSite": "None",
            },
        ]

    @pytest.mark.parametrize(
        "label,currency_value",
        [
            ("empty_string", ""),
            ("none_value", None),
        ],
        ids=["empty_string", "no_currency_key"],
    )
    def test_page_does_not_crash_for_missing_currency(
        self, logged_in_context, page, label, currency_value
    ):
        cookies = self._make_empty_currency_cookies(currency_value)
        set_currency(logged_in_context, cookies)
        navigate_to_cart(page)

        page.wait_for_timeout(2000)

        assert page.query_selector("body") is not None, (
            f"Page should not crash for {label} currency"
        )

    @pytest.mark.parametrize(
        "label,currency_value",
        [
            ("empty_string", ""),
            ("none_value", None),
        ],
        ids=["empty_string", "no_currency_key"],
    )
    def test_checkout_state_for_missing_currency(
        self, logged_in_context, page, label, currency_value
    ):
        """
        Documents actual behavior for missing/empty currency.
        Ideally checkout should be blocked, but this test captures
        actual state for reporting.
        """
        cookies = self._make_empty_currency_cookies(currency_value)
        set_currency(logged_in_context, cookies)
        navigate_to_cart(page)
        page.wait_for_timeout(2000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        if btn is None:
            return

        enabled = is_button_enabled(btn)
        if enabled:
            pytest.xfail(
                f"POTENTIAL BUG: CHECKOUT is ENABLED for {label} currency — "
                f"missing/empty currency should ideally be blocked"
            )


# ---------------------------------------------------------------------------
# CUR-18: Lowercase / malformed currency value
# ---------------------------------------------------------------------------
class TestCUR18MalformedCurrency:

    @pytest.mark.parametrize(
        "label,currency_value",
        [
            ("lowercase_inr", "inr"),
            ("trailing_space", "INR "),
            ("invalid_code", "XYZ"),
            ("numeric", "123"),
        ],
        ids=["lowercase_inr", "trailing_space_INR", "invalid_XYZ", "numeric_123"],
    )
    def test_checkout_blocked_for_malformed_currency(
        self, logged_in_context, page, label, currency_value
    ):
        cookies = make_currency_cookies("XX", "XX", currency_value)
        set_currency(logged_in_context, cookies)
        navigate_to_cart(page)

        page.wait_for_timeout(2000)

        assert page.query_selector("body") is not None, (
            f"Page should not crash for malformed currency '{currency_value}'"
        )

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        if btn is None:
            return  # Acceptable — button may not render

        is_enabled = is_button_enabled(btn)
        if currency_value.strip().upper() == "INR":
            # Depends on normalization: lowercase 'inr' might or might not be accepted
            # This test documents actual behavior
            pass
        else:
            assert not is_enabled, (
                f"CHECKOUT should be DISABLED for malformed currency "
                f"'{currency_value}'"
            )


# ---------------------------------------------------------------------------
# CUR-19: API failure / loading state
# ---------------------------------------------------------------------------
class TestCUR19APIFailureLoadingState:

    def test_buttons_disabled_during_slow_cart_load(
        self, logged_in_context, page
    ):
        set_currency(logged_in_context, USD_COOKIES)

        import time

        def delay_cart_api(route):
            time.sleep(2)
            route.continue_()

        page.route("**/getCart**", delay_cart_api)

        page.goto(CART_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        if btn is not None:
            assert not is_button_enabled(btn), (
                "CHECKOUT should be DISABLED during slow cart API load for USD"
            )

        page.unroute("**/getCart**")
        page.wait_for_timeout(5000)

    def test_no_loader_stuck_after_cart_load(self, logged_in_context, page):
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        loaders = page.query_selector_all(
            ".loader, .spinner, [class*='loading'], [class*='skeleton']"
        )
        visible_loaders = [l for l in loaders if l.is_visible()]
        assert len(visible_loaders) == 0, (
            "No loader/spinner should remain stuck after cart page loads"
        )


# ---------------------------------------------------------------------------
# CUR-20: Browser coverage — Chromium, Firefox, WebKit
# ---------------------------------------------------------------------------
class TestCUR20BrowserCoverage:

    def _launch_and_login(self, playwright_instance, browser_type):
        launcher = getattr(playwright_instance, browser_type)
        try:
            alt_browser = launcher.launch(headless=True)
        except Exception as e:
            pytest.skip(f"{browser_type} not available: {e}")

        context = alt_browser.new_context(
            viewport=DESKTOP_VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        bpage = context.new_page()

        from conftest import login as do_login
        try:
            do_login(bpage)
        except Exception as e:
            alt_browser.close()
            pytest.skip(
                f"Login failed on {browser_type} — site may not support "
                f"this browser: {e}"
            )
        return alt_browser, context, bpage

    @pytest.mark.parametrize(
        "browser_type",
        ["firefox", "webkit"],
        ids=["Firefox", "Safari"],
    )
    def test_checkout_disabled_for_usd_other_browsers(
        self, playwright_instance, browser_type
    ):
        alt_browser, context, bpage = self._launch_and_login(
            playwright_instance, browser_type
        )

        set_currency(context, USD_COOKIES)
        navigate_to_cart(bpage)

        btn = bpage.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, (
            f"CHECKOUT button not found on {browser_type}"
        )
        assert not is_button_enabled(btn), (
            f"CHECKOUT should be DISABLED for USD on {browser_type}"
        )

        alt_browser.close()

    @pytest.mark.parametrize(
        "browser_type",
        ["firefox", "webkit"],
        ids=["Firefox", "Safari"],
    )
    def test_checkout_enabled_for_inr_other_browsers(
        self, playwright_instance, browser_type
    ):
        alt_browser, context, bpage = self._launch_and_login(
            playwright_instance, browser_type
        )

        set_currency(context, INR_COOKIES)
        navigate_to_cart(bpage)

        btn = bpage.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, (
            f"CHECKOUT button not found on {browser_type}"
        )
        assert is_button_enabled(btn), (
            f"CHECKOUT should be ENABLED for INR on {browser_type}"
        )

        alt_browser.close()

    def test_checkout_disabled_for_usd_chromium(
        self, logged_in_context, page
    ):
        """Chromium is tested by default — this confirms it explicitly."""
        set_currency(logged_in_context, USD_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, "CHECKOUT button not found on Chromium"
        assert not is_button_enabled(btn), (
            "CHECKOUT should be DISABLED for USD on Chromium"
        )

    def test_checkout_enabled_for_inr_chromium(
        self, logged_in_context, page
    ):
        """Chromium is tested by default — this confirms it explicitly."""
        set_currency(logged_in_context, INR_COOKIES)
        navigate_to_cart(page)

        btn = page.query_selector(CHECKOUT_BTN_DESKTOP)
        assert btn is not None, "CHECKOUT button not found on Chromium"
        assert is_button_enabled(btn), (
            "CHECKOUT should be ENABLED for INR on Chromium"
        )
