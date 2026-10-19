from __future__ import annotations

import pytest

from amatch_checker.analysis import (
    analyze_html,
    count_words,
    has_email_in_text,
    has_phone_in_text,
)
from amatch_checker.i18n import CATEGORIES, SUPPORTED_LANGS


def statuses(html: str, lang: str = "en") -> dict[str, str]:
    return {check.name: check.status for check in analyze_html(html, "https://x.ch", lang).checks}  # type: ignore[arg-type]


def page(body: str, head: str = "") -> str:
    return f"<html><head>{head}</head><body>{body}</body></html>"


class TestReport:
    def test_strong_ad_passes_every_check(self, strong_ad: str) -> None:
        report = analyze_html(strong_ad, "https://example.ch/job", "de")
        assert report.overall == 100
        assert report.total_passed == report.total_checks == 16
        assert all(c.status == "pass" for c in report.checks)

    def test_weak_ad_scores_zero(self, weak_ad: str) -> None:
        report = analyze_html(weak_ad, "https://example.ch/job", "de")
        assert report.overall == 0
        assert [c.status for c in report.weakest_checks()] == ["fail"] * 4

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_categories_are_localized_and_complete(self, strong_ad: str, lang: str) -> None:
        report = analyze_html(strong_ad, "https://example.ch", lang)  # type: ignore[arg-type]
        assert list(report.categories) == list(CATEGORIES[lang].values())  # type: ignore[index]
        assert sum(c.total for c in report.categories.values()) == 16

    def test_json_shape_matches_frontend_contract(self, strong_ad: str) -> None:
        data = analyze_html(strong_ad, "https://example.ch", "en", load_time=0.123).to_dict()
        assert set(data) == {
            "url", "overall", "categories", "checks", "total_passed", "total_checks", "load_time",
        }  # fmt: skip
        assert data["load_time"] == 0.12
        category = next(iter(data["categories"].values()))  # type: ignore[attr-defined]
        assert set(category) == {"score", "passed", "total"}
        assert set(data["checks"][0]) == {"category", "name", "status", "finding"}  # type: ignore[index]

    def test_partial_counts_as_not_passed(self) -> None:
        # Only "pass" contributes to a category score; "partial" is a soft miss.
        report = analyze_html(page("<p>ferien</p>"), "https://x.ch", "en")
        benefits = report.categories["Employer benefits"]
        assert (benefits.passed, benefits.total, benefits.score) == (1, 4, 25)


class TestIndividualChecks:
    @pytest.mark.parametrize(
        ("words", "expected"),
        [(149, "fail"), (150, "pass"), (700, "pass"), (701, "partial")],
    )
    def test_text_length_thresholds(self, words: int, expected: str) -> None:
        assert statuses(page("wort " * words))["Text length"] == expected

    @pytest.mark.parametrize(
        ("items", "expected"), [(0, "fail"), (1, "partial"), (2, "partial"), (3, "pass")]
    )
    def test_structure_counts_list_items(self, items: int, expected: str) -> None:
        assert statuses(page("<ul>" + "<li>x</li>" * items + "</ul>"))["Structure"] == expected

    @pytest.mark.parametrize(
        ("required", "expected"), [(4, "pass"), (5, "partial"), (7, "partial"), (8, "fail")]
    )
    def test_long_forms_are_penalized(self, required: int, expected: str) -> None:
        form = "<form>" + "<input required>" * required + "</form>"
        assert statuses(page(form))["Application form"] == expected

    def test_no_form_means_direct_contact(self) -> None:
        assert statuses(page("<p>x</p>"))["Application form"] == "pass"

    def test_title_needs_some_substance(self) -> None:
        assert statuses(page("", "<title>Job</title>"))["Meaningful title"] == "fail"
        assert statuses(page("", "<title>Maler EFZ in Thun</title>"))["Meaningful title"] == "pass"

    def test_contact_is_found_in_links_and_plain_text(self) -> None:
        assert (
            statuses(page('<a href="mailto:a@b.ch">Mail</a>'))["Direct contact visible"] == "pass"
        )
        assert statuses(page("Telefon 031 859 77 77"))["Direct contact visible"] == "pass"
        assert statuses(page("Keine Angaben"))["Direct contact visible"] == "fail"

    def test_whatsapp_missing_is_only_partial(self) -> None:
        assert statuses(page("x"))["WhatsApp option"] == "partial"
        assert statuses(page('<a href="https://wa.me/41">Chat</a>'))["WhatsApp option"] == "pass"

    def test_social_preview_needs_two_open_graph_tags(self) -> None:
        one = '<meta property="og:title" content="x">'
        two = one + '<meta property="og:image" content="y">'
        assert statuses(page("", one))["Shareable on social media"] == "fail"
        assert statuses(page("", two))["Shareable on social media"] == "pass"

    def test_finding_text_includes_values(self) -> None:
        report = analyze_html(page("<img src=a><img src=b>"), "https://x.ch", "en")
        images = next(c for c in report.checks if c.name == "Images present")
        assert images.finding == "2 image(s) on the page"


class TestTextHelpers:
    @pytest.mark.parametrize(
        "text",
        ["031 859 77 77", "+41 31 859 77 77", "0041 31 859 77 77", "+41 (0)31 859 77 77",
         "079.123.45.67", "079-123-45-67"],
    )  # fmt: skip
    def test_recognizes_swiss_phone_numbers(self, text: str) -> None:
        assert has_phone_in_text(f"Ruf an: {text}")

    @pytest.mark.parametrize("text", ["PLZ 3011", "Jahrgang 2026", "CHF 5800"])
    def test_ignores_other_numbers(self, text: str) -> None:
        assert not has_phone_in_text(text)

    def test_email_detection(self) -> None:
        assert has_email_in_text("jobs@firma.ch")
        assert not has_email_in_text("firma at ch")

    def test_count_words(self) -> None:
        assert count_words("  eins zwei\n drei ") == 3
