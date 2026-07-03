"""Tests for false positive filtering in e-commerce comparison reports."""

import io
import pytest
from PIL import Image

from scraper import ElementData, SectionData
from atd_analyzer import (
    check_typography_hierarchy,
    check_type_scale,
    check_text_case,
    check_element_consistency,
    check_color_consistency,
    check_font_weight_consistency,
    compare_element_styles,
    _is_product_content,
    _is_brand_name,
    _classify_case,
    _colors_similar,
)


def _make_screenshot(width=1920, height=3000):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_element(tag, text, font_size="16px", font_weight="400", selector=None, y=100,
                   color="rgb(0, 0, 0)", font_family="Roboto", text_transform="none",
                   background_color="rgba(0, 0, 0, 0)", border="none"):
    return ElementData(
        tag=tag,
        selector=selector or f"{tag}.{text[:10].replace(' ', '_')}",
        text=text,
        bounding_box={"x": 100, "y": y, "width": 200, "height": 30},
        font_family=font_family,
        font_size=font_size,
        font_weight=font_weight,
        font_style="normal",
        line_height="24px",
        letter_spacing="normal",
        text_align="left",
        color=color,
        margin="0px",
        padding="0px",
        position="static",
        display="block",
        text_transform=text_transform,
        background_color=background_color,
        border=border,
        text_decoration="none",
    )


SECTIONS = [SectionData(name="Content", y_start=0, y_end=3000, crop_bytes=b"")]
SCREENSHOT = _make_screenshot()


class TestTypographyHierarchyPriceFiltering:
    def test_price_text_not_flagged_as_hierarchy_violation(self):
        elements = [
            _make_element("h2", "Discover Our Campaign", font_size="16px", font_weight="400", y=50),
            _make_element("span", "₹25,680", font_size="14px", font_weight="600", y=200),
            _make_element("span", "₹23,920", font_size="14px", font_weight="600", y=300),
            _make_element("span", "₹14,274", font_size="14px", font_weight="600", y=400),
            _make_element("span", "₹10,374", font_size="14px", font_weight="600", y=500),
        ]
        diffs = check_typography_hierarchy(elements, SCREENSHOT, SECTIONS, "https://example.com")

        hierarchy_violations = [d for d in diffs if d.property == "hierarchy-violation"
                                and "bolder" in d.human_description.lower()]
        assert len(hierarchy_violations) == 0, (
            f"Price text should not be flagged as hierarchy violation, got: "
            f"{[d.human_description for d in hierarchy_violations]}"
        )

    def test_real_hierarchy_violation_still_detected(self):
        elements = [
            _make_element("h2", "Section Title", font_size="16px", font_weight="400", y=50),
            _make_element("span", "Regular body text here", font_size="14px", font_weight="600", y=200),
            _make_element("span", "Another body text span", font_size="14px", font_weight="600", y=300),
            _make_element("span", "Third body text item", font_size="14px", font_weight="600", y=400),
            _make_element("span", "Fourth body text item", font_size="14px", font_weight="600", y=500),
        ]
        diffs = check_typography_hierarchy(elements, SCREENSHOT, SECTIONS, "https://example.com")

        hierarchy_violations = [d for d in diffs if d.property == "hierarchy-violation"
                                and "bolder" in d.human_description.lower()]
        assert len(hierarchy_violations) > 0, "Real hierarchy violation should still be detected"


class TestIsBrandName:
    def test_all_caps_brand(self):
        assert _is_brand_name("RAY-BAN") is True

    def test_multi_word_brand(self):
        assert _is_brand_name("EMPORIO ARMANI") is True

    def test_single_word_brand(self):
        assert _is_brand_name("BURBERRY") is True

    def test_title_case_not_brand(self):
        assert _is_brand_name("Shop Now") is False

    def test_sentence_not_brand(self):
        assert _is_brand_name("Discover Our Campaign Selection") is False

    def test_short_text_not_brand(self):
        assert _is_brand_name("A") is False

    def test_numbers_not_brand(self):
        assert _is_brand_name("12345") is False

    def test_long_caps_not_brand(self):
        assert _is_brand_name("THIS IS A VERY LONG SENTENCE IN ALL CAPS") is False


class TestTypeScalePriceFiltering:
    def test_price_text_not_flagged_as_off_scale(self):
        elements = [
            _make_element("span", "₹25,680", font_size="13px", y=200),
            _make_element("span", "₹23,920", font_size="13px", y=300),
            _make_element("span", "₹14,274", font_size="13px", y=400),
        ]
        diffs = check_type_scale(elements, SCREENSHOT, SECTIONS, "https://example.com")

        off_scale = [d for d in diffs if d.property == "off-scale-font"]
        assert len(off_scale) == 0, (
            f"Price text should not be flagged as off-scale font, got: "
            f"{[d.human_description for d in off_scale]}"
        )

    def test_real_off_scale_still_detected(self):
        elements = [
            _make_element("span", "Regular text content", font_size="13px", y=200),
            _make_element("span", "More regular text", font_size="13px", y=300),
        ]
        diffs = check_type_scale(elements, SCREENSHOT, SECTIONS, "https://example.com")

        off_scale = [d for d in diffs if d.property == "off-scale-font"]
        assert len(off_scale) > 0, "Real off-scale font should still be detected"


class TestTextCaseBrandFiltering:
    def test_brand_names_not_flagged_as_case_mismatch(self):
        elements = [
            _make_element("a", "RAY-BAN", y=100, selector="a.brand1"),
            _make_element("a", "BURBERRY", y=200, selector="a.brand2"),
            _make_element("a", "OAKLEY", y=300, selector="a.brand3"),
            _make_element("a", "Shop Now", y=400, selector="a.shop1"),
            _make_element("a", "Shop Now", y=500, selector="a.shop2"),
            _make_element("a", "Shop Now", y=600, selector="a.shop3"),
        ]
        diffs = check_text_case(elements, SCREENSHOT, SECTIONS, "https://example.com")

        case_mismatches = [d for d in diffs if d.property == "case-mismatch"]
        assert len(case_mismatches) == 0, (
            f"Brand names should not be flagged as case mismatch, got: "
            f"{[d.human_description for d in case_mismatches]}"
        )

    def test_real_case_mismatch_still_detected(self):
        elements = [
            _make_element("a", "click here", y=100, selector="a.link1"),
            _make_element("a", "learn more", y=200, selector="a.link2"),
            _make_element("a", "read more", y=300, selector="a.link3"),
            _make_element("a", "Shop Now", y=400, selector="a.link4"),
            _make_element("a", "Contact Us", y=500, selector="a.link5"),
            _make_element("a", "About Us", y=600, selector="a.link6"),
        ]
        diffs = check_text_case(elements, SCREENSHOT, SECTIONS, "https://example.com")

        case_mismatches = [d for d in diffs if d.property == "case-mismatch"]
        assert len(case_mismatches) > 0, "Real case mismatch should still be detected"


class TestElementConsistencyPriceFiltering:
    def test_price_elements_not_flagged_as_inconsistent(self):
        elements = [
            _make_element("a", "₹25,680", font_size="14px", font_weight="600",
                          color="rgb(153, 0, 0)", y=100, selector="a.price1"),
            _make_element("a", "₹23,920", font_size="14px", font_weight="600",
                          color="rgb(153, 0, 0)", y=200, selector="a.price2"),
            _make_element("a", "₹32,100", font_size="12px", font_weight="400",
                          color="rgb(100, 100, 100)", y=300, selector="a.orig1"),
            _make_element("a", "About Us", font_size="14px", font_weight="400",
                          color="rgb(0, 0, 0)", y=400, selector="a.about"),
            _make_element("a", "Contact", font_size="14px", font_weight="400",
                          color="rgb(0, 0, 0)", y=500, selector="a.contact"),
            _make_element("a", "Help", font_size="14px", font_weight="400",
                          color="rgb(0, 0, 0)", y=600, selector="a.help"),
        ]
        diffs = check_element_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        inconsistent = [d for d in diffs if d.property == "inconsistent-style"
                        and any(price in d.human_description for price in ["₹", "$", "€"])]
        assert len(inconsistent) == 0, (
            f"Price elements should not cause inconsistency flags, got: "
            f"{[d.human_description for d in inconsistent]}"
        )


class TestElementConsistencySmallWeightDiff:
    def test_small_weight_diff_not_flagged(self):
        """Footer section headings with weight 500 vs regular links at 400 should not be flagged."""
        elements = (
            [_make_element("a", f"Link {i}", font_weight="400", y=100 + i * 30, selector=f"a.link{i}")
             for i in range(10)]
            + [_make_element("a", "Quick Links", font_weight="500", y=500, selector="a.ql"),
               _make_element("a", "About Us", font_weight="500", y=530, selector="a.about"),
               _make_element("a", "Help & Info", font_weight="500", y=560, selector="a.help"),
               _make_element("a", "Brands", font_weight="500", y=590, selector="a.brands")]
        )
        diffs = check_element_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        weight_issues = [d for d in diffs if d.property == "inconsistent-style"
                         and "font-weight" in d.human_description]
        assert len(weight_issues) == 0, (
            f"Small font-weight difference (400 vs 500) should not be flagged, got: "
            f"{[d.human_description for d in weight_issues]}"
        )

    def test_large_weight_diff_still_flagged(self):
        """Links with weight 700 vs majority 400 should still be flagged."""
        elements = (
            [_make_element("a", f"Link {i}", font_weight="400", y=100 + i * 30, selector=f"a.link{i}")
             for i in range(10)]
            + [_make_element("a", "Bold Link A", font_weight="700", y=500, selector="a.bold1"),
               _make_element("a", "Bold Link B", font_weight="700", y=530, selector="a.bold2"),
               _make_element("a", "Bold Link C", font_weight="700", y=560, selector="a.bold3")]
        )
        diffs = check_element_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        weight_issues = [d for d in diffs if d.property == "inconsistent-style"
                         and "font-weight" in d.human_description]
        assert len(weight_issues) > 0, "Large font-weight difference (400 vs 700) should still be flagged"


class TestColorConsistencyPriceFiltering:
    def test_price_colors_not_flagged_as_inconsistent(self):
        elements = [
            _make_element("a", "₹25,680", color="rgb(153, 0, 0)", y=100, selector="a.sale1"),
            _make_element("a", "₹23,920", color="rgb(153, 0, 0)", y=200, selector="a.sale2"),
            _make_element("a", "₹14,274", color="rgb(153, 0, 0)", y=300, selector="a.sale3"),
            _make_element("a", "About Us", color="rgb(0, 0, 0)", y=400, selector="a.about"),
            _make_element("a", "Contact", color="rgb(0, 0, 0)", y=500, selector="a.contact"),
            _make_element("a", "Help", color="rgb(0, 0, 0)", y=600, selector="a.help"),
        ]
        diffs = check_color_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        color_issues = [d for d in diffs if d.property == "color-inconsistency"]
        assert len(color_issues) == 0, (
            f"Price element colors should not be flagged as inconsistent, got: "
            f"{[d.human_description for d in color_issues]}"
        )


class TestFontWeightConsistencyPriceFiltering:
    def test_price_weights_not_flagged_as_inconsistent(self):
        elements = [
            _make_element("span", "₹25,680", font_weight="600", y=100, selector="span.p1"),
            _make_element("span", "₹23,920", font_weight="600", y=200, selector="span.p2"),
            _make_element("span", "Regular text one", font_weight="400", y=300, selector="span.t1"),
            _make_element("span", "Regular text two", font_weight="400", y=400, selector="span.t2"),
            _make_element("span", "Regular text three", font_weight="400", y=500, selector="span.t3"),
        ]
        diffs = check_font_weight_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        weight_issues = [d for d in diffs if d.property == "weight-inconsistency"]
        assert len(weight_issues) == 0, (
            f"Price font weights should not be flagged as inconsistent, got: "
            f"{[d.human_description for d in weight_issues]}"
        )


class TestCrossPageStyleListItems:
    def test_li_elements_not_compared_cross_page(self):
        """<li> nav items should not be compared cross-page since their computed
        styles often differ from the visually rendered inner element styles."""
        live_elements = [
            _make_element("li", "Women", font_weight="400", y=40, selector="li.women"),
            _make_element("li", "Ray-Ban", font_weight="400", y=40, selector="li.rayban"),
            _make_element("li", "Brands", font_weight="400", y=40, selector="li.brands"),
        ]
        uat_elements = [
            _make_element("li", "Women", font_weight="600", y=40, selector="li.women"),
            _make_element("li", "Ray-Ban", font_weight="600", y=40, selector="li.rayban"),
            _make_element("li", "Brands", font_weight="600", y=40, selector="li.brands"),
        ]
        diffs = compare_element_styles(
            live_elements, uat_elements,
            SCREENSHOT, SCREENSHOT,
            SECTIONS, SECTIONS,
            "https://live.example.com", "https://uat.example.com",
        )

        li_diffs = [d for d in diffs if "li" in d.element.lower() or "women" in d.human_description.lower()]
        assert len(li_diffs) == 0, (
            f"<li> elements should not be compared cross-page, got: "
            f"{[d.human_description for d in li_diffs]}"
        )


class TestElementConsistencyRatioThreshold:
    def test_large_outlier_group_not_flagged(self):
        """When ~30% of links use a different style (nav vs footer), it's intentional."""
        nav_links = [_make_element("a", f"Nav {i}", font_family="Inter", font_size="14px",
                                    color="rgb(14, 14, 14)", y=44, selector=f"a.nav{i}")
                     for i in range(14)]
        footer_links = [_make_element("a", f"Footer Link {i}", font_family="Roboto", font_size="12px",
                                       color="rgb(85, 85, 85)", y=4000 + i * 30, selector=f"a.foot{i}")
                        for i in range(30)]
        elements = nav_links + footer_links

        diffs = check_element_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        font_family_issues = [d for d in diffs if d.property == "inconsistent-style"
                              and "font-family" in d.human_description]
        assert len(font_family_issues) == 0, (
            f"Large outlier group (nav vs footer links) should not be flagged, got: "
            f"{[d.human_description for d in font_family_issues]}"
        )


class TestColorConsistencyRatioThreshold:
    def test_large_color_group_not_flagged(self):
        """Nav links (dark) vs footer links (gray) should not be flagged."""
        nav_links = [_make_element("a", f"Nav {i}", color="rgb(14, 14, 14)",
                                    y=44, selector=f"a.nav{i}")
                     for i in range(10)]
        footer_links = [_make_element("a", f"Footer {i}", color="rgb(85, 85, 85)",
                                       y=4000 + i * 30, selector=f"a.foot{i}")
                        for i in range(20)]
        elements = nav_links + footer_links

        diffs = check_color_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        color_issues = [d for d in diffs if d.property == "color-inconsistency"]
        assert len(color_issues) == 0, (
            f"Large color group (nav vs footer) should not be flagged, got: "
            f"{[d.human_description for d in color_issues]}"
        )


class TestFontWeightConsistencyThreshold:
    def test_small_weight_diff_not_flagged(self):
        """Font-weight 500 vs 400 (diff=100) should not be flagged."""
        elements = (
            [_make_element("a", f"Footer Link {i}", font_weight="400", y=4000 + i * 30,
                           selector=f"a.fl{i}")
             for i in range(8)]
            + [_make_element("a", "Quick Links", font_weight="500", y=3919, selector="a.ql"),
               _make_element("a", "Brands", font_weight="500", y=3920, selector="a.br"),
               _make_element("a", "About Us", font_weight="500", y=3921, selector="a.ab"),
               _make_element("a", "Help & Info", font_weight="500", y=3922, selector="a.hi")]
        )
        diffs = check_font_weight_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")

        weight_issues = [d for d in diffs if d.property == "weight-inconsistency"]
        assert len(weight_issues) == 0, (
            f"Small weight diff (500 vs 400) should not be flagged, got: "
            f"{[d.human_description for d in weight_issues]}"
        )


class TestTextCaseEdgeCases:
    def test_email_address_not_flagged(self):
        """Email addresses are always lowercase — should be excluded."""
        elements = [
            _make_element("a", "Our Story", y=100, selector="a.story"),
            _make_element("a", "Contact Us", y=200, selector="a.contact"),
            _make_element("a", "About Us", y=300, selector="a.about"),
            _make_element("a", "support@sunglasshut.in", y=400, selector="a.email"),
        ]
        diffs = check_text_case(elements, SCREENSHOT, SECTIONS, "https://example.com")

        case_issues = [d for d in diffs if d.property == "case-mismatch"
                       and "support@" in d.human_description]
        assert len(case_issues) == 0, (
            f"Email addresses should not be flagged as case mismatch, got: "
            f"{[d.human_description for d in case_issues]}"
        )

    def test_parenthetical_labels_not_flagged(self):
        """Text with '(TOP BRAND)' or '(New Arrival)' labels should be excluded."""
        elements = [
            _make_element("a", "Our Story", y=100, selector="a.story"),
            _make_element("a", "Contact Us", y=200, selector="a.contact"),
            _make_element("a", "Ray-Ban (TOP BRAND)", y=300, selector="a.rb"),
            _make_element("a", "Prada (TOP BRAND)", y=400, selector="a.prada"),
        ]
        diffs = check_text_case(elements, SCREENSHOT, SECTIONS, "https://example.com")

        label_issues = [d for d in diffs if d.property == "case-mismatch"
                        and "TOP BRAND" in d.human_description]
        assert len(label_issues) == 0, (
            f"Parenthetical labels should not cause case mismatch, got: "
            f"{[d.human_description for d in label_issues]}"
        )


class TestClassifyCase:
    def test_title_case_with_prepositions(self):
        assert _classify_case("Find a Store") == "Title Case"

    def test_title_case_with_of(self):
        assert _classify_case("Terms of Service") == "Title Case"

    def test_title_case_with_and(self):
        assert _classify_case("Terms and Conditions") == "Title Case"

    def test_simple_title_case(self):
        assert _classify_case("About Us") == "Title Case"

    def test_all_caps(self):
        assert _classify_case("SALE") == "ALL CAPS"


class TestIsProductContent:
    def test_price_with_rupee_symbol(self):
        assert _is_product_content("₹25,680") is True

    def test_price_with_dollar_symbol(self):
        assert _is_product_content("$99.99") is True

    def test_shop_now_text(self):
        assert _is_product_content("Shop Now") is True

    def test_add_to_cart(self):
        assert _is_product_content("Add to Cart") is True

    def test_regular_text_not_product(self):
        assert _is_product_content("Discover Our Collection") is False

    def test_heading_not_product(self):
        assert _is_product_content("Section Title") is False


class TestTypographyHierarchySaleLabel:
    def test_sale_label_not_flagged_as_hierarchy_violation(self):
        elements = [
            _make_element("h2", "Discover Our Campaign", font_size="16px", font_weight="400", y=50),
            _make_element("span", "SALE", font_size="14px", font_weight="500", y=200),
            _make_element("span", "SALE", font_size="14px", font_weight="500", y=300),
            _make_element("span", "SALE", font_size="14px", font_weight="500", y=400),
        ]
        diffs = check_typography_hierarchy(elements, SCREENSHOT, SECTIONS, "https://example.com")
        hierarchy_violations = [d for d in diffs if d.property == "hierarchy-violation"
                                and "bolder" in d.human_description.lower()]
        assert len(hierarchy_violations) == 0, (
            f"'SALE' label should not be flagged, got: {[d.human_description for d in hierarchy_violations]}"
        )

    def test_account_nav_label_not_flagged_as_hierarchy_violation(self):
        elements = [
            _make_element("h2", "Trending Now", font_size="16px", font_weight="400", y=50),
            _make_element("span", "Account", font_size="14px", font_weight="600", y=100),
            _make_element("span", "Account", font_size="14px", font_weight="600", y=200),
            _make_element("span", "Account", font_size="14px", font_weight="600", y=300),
        ]
        diffs = check_typography_hierarchy(elements, SCREENSHOT, SECTIONS, "https://example.com")
        hierarchy_violations = [d for d in diffs if d.property == "hierarchy-violation"
                                and "bolder" in d.human_description.lower()]
        assert len(hierarchy_violations) == 0, (
            f"'Account' nav label should not be flagged, got: {[d.human_description for d in hierarchy_violations]}"
        )


class TestColorsSimilarTolerance:
    def test_near_identical_colors_are_similar(self):
        assert _colors_similar((0, 0, 0), (14, 14, 14)) is True

    def test_different_colors_not_similar(self):
        assert _colors_similar((0, 0, 0), (51, 51, 51)) is False


class TestElementConsistencyNearColorFP:
    def test_near_identical_button_colors_not_flagged(self):
        elements = [
            _make_element("button", "Product Info", color="rgb(14, 14, 14)", y=100),
            _make_element("button", "Product Desc", color="rgb(14, 14, 14)", y=200),
            _make_element("button", "Reviews", color="rgb(14, 14, 14)", y=300),
            _make_element("button", "Shipping", color="rgb(0, 0, 0)", y=400),
        ]
        diffs = check_element_consistency(elements, SCREENSHOT, SECTIONS, "https://example.com")
        color_diffs = [d for d in diffs if "color" in d.property.lower()
                       and "rgb(0,0,0)" in (d.value1 or "")]
        assert len(color_diffs) == 0, (
            f"Near-identical colors should not be flagged, got: {[d.human_description for d in color_diffs]}"
        )
