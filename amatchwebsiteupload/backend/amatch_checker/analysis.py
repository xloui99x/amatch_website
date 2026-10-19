"""Rule-based content audit of a job ad.

Deliberately not an SEO or performance scan: the checks look at what a
tradesperson sees when reading the ad, grouped into four categories (role
description, application process, employer benefits, reach). Each category
scores 0–100 as the share of passed checks. Everything is keyword and
structure detection, so the result is reported as "first pointers", not as a
judgement of writing quality.

``analyze_html`` is a pure function of the HTML and therefore easy to test;
fetching lives in :mod:`safe_fetch`.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from bs4 import BeautifulSoup

from .i18n import CATEGORIES, CATEGORY_KEYS, CHECK_NAMES, FINDINGS, Lang

Status = Literal["pass", "partial", "fail"]

# ── Detection rules ──────────────────────────────────────────────────────────

SALARY_WORDS = ("lohn", "gehalt", "salär", "chf", "fr.", "salary", "salaire")
TRAINING_WORDS = (
    "weiterbildung", "kurse", "weiterentwicklung", "perspektive", "aufstieg", "training",
    "formation",
)  # fmt: skip
TEAM_WORDS = ("team", "kolleg", "kultur", "zusammenarbeit", "familiär", "atmosphäre", "équipe")
EXTRAS_WORDS = (
    "ferien", "urlaub", "bonus", "13.", "firmenfahrzeug", "pensionskasse", "flexibel", "flexible",
    "vacances",
)  # fmt: skip
CTA_WORDS = (
    "bewerben", "bewerbung", "kontakt", "melden sie sich", "melde dich", "jetzt bewerben",
    "apply", "contact us", "postuler", "candidature", "contactez",
)  # fmt: skip
# Words that address the reader directly (formal or informal); matched with
# surrounding spaces so "sie" does not hit inside other words.
DIRECT_ADDRESS_WORDS = (
    " sie ", " ihr", " ihre", " du ", " dein", " deine", " your ", " you ", " vous ", " votre",
)  # fmt: skip
CONCRETE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b\d{1,3}\s?%",
        r"\befz\b",
        r"\bcfc\b",
        r"\blehre\b",
        r"\bausbildung\b",
        r"\bpensum\b",
        r"\bvollzeit\b",
        r"\bteilzeit\b",
        r"\bfull.?time\b",
        r"\bpart.?time\b",
    )
)

# Contact details are often plain text ("Telefon 031 859 77 77") rather than
# mailto:/tel: links, so the visible text is scanned as well. Covers Swiss
# local numbers (0XX XXX XX XX) and international ones (+41 / 0041) with any
# mix of spaces, dots or hyphens.
PHONE_TEXT_RE = re.compile(
    r"(?:\+41|0041)[\s.\-]?\(?0?\)?[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}"
    r"|0\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}"
)
EMAIL_TEXT_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Thresholds
IDEAL_WORD_RANGE = (150, 700)
MIN_LIST_ITEMS = 3
MIN_TITLE_LENGTH = 12
MAX_EASY_FORM_FIELDS = 4
MAX_OK_FORM_FIELDS = 7
MIN_DIRECT_ADDRESS_HITS = 3
MIN_OPEN_GRAPH_TAGS = 2


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Check:
    category: str
    name: str
    status: Status
    finding: str


@dataclass(frozen=True)
class CategoryScore:
    score: int
    passed: int
    total: int


@dataclass(frozen=True)
class Report:
    url: str
    overall: int
    categories: dict[str, CategoryScore]
    checks: list[Check]
    total_passed: int
    total_checks: int
    load_time: float

    def to_dict(self) -> dict[str, object]:
        """JSON shape consumed by ``script.js``; keep keys stable."""
        return asdict(self)

    def weakest_checks(self, limit: int = 4) -> list[Check]:
        """Failed checks first, then partial ones."""
        weak = [check for check in self.checks if check.status != "pass"]
        weak.sort(key=lambda check: 0 if check.status == "fail" else 1)
        return weak[:limit]


@dataclass
class _Collector:
    lang: Lang
    checks: list[Check] = field(default_factory=list)

    def add(self, key: str, category: str, status: Status, finding: str, **values: object) -> None:
        self.checks.append(
            Check(
                category=CATEGORIES[self.lang][category],
                name=CHECK_NAMES[key][self.lang],
                status=status,
                finding=FINDINGS[self.lang][finding].format(**values),
            )
        )

    def add_binary(self, key: str, category: str, ok: bool, *, otherwise: Status = "fail") -> None:
        """Shorthand for checks with a fixed pass text and a fixed miss text."""
        status: Status = "pass" if ok else otherwise
        self.add(key, category, status, f"{key}_{status}")


# ── Analysis ─────────────────────────────────────────────────────────────────


def analyze_html(html: str, url: str, lang: Lang, load_time: float = 0.0) -> Report:
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(" ", strip=True)
    text = f" {body_text.lower()} "
    out = _Collector(lang)

    _check_task_description(soup, body_text, text, out)
    _check_application_process(soup, body_text, text, out)
    _check_benefits(text, out)
    _check_reach(soup, text, out)

    return _aggregate(out.checks, url, lang, load_time)


def _check_task_description(
    soup: BeautifulSoup, body_text: str, text: str, out: _Collector
) -> None:
    words = count_words(body_text)
    low, high = IDEAL_WORD_RANGE
    if low <= words <= high:
        out.add("text_length", "task", "pass", "text_length_pass", n=words)
    elif words < low:
        out.add("text_length", "task", "fail", "text_length_fail", n=words)
    else:
        out.add("text_length", "task", "partial", "text_length_partial", n=words)

    out.add_binary("concrete", "task", any(p.search(text) for p in CONCRETE_PATTERNS))

    items = len(soup.find_all("li"))
    if items >= MIN_LIST_ITEMS:
        out.add("structure", "task", "pass", "structure_pass", n=items)
    elif items >= 1:
        out.add("structure", "task", "partial", "structure_partial", n=items)
    else:
        out.add("structure", "task", "fail", "structure_fail")

    title = page_title(soup)
    if len(title) >= MIN_TITLE_LENGTH:
        out.add("title", "task", "pass", "title_pass", title=title)
    else:
        out.add("title", "task", "fail", "title_fail")


def _check_application_process(
    soup: BeautifulSoup, body_text: str, text: str, out: _Collector
) -> None:
    has_mail = _has_link(soup, r"^mailto:") or has_email_in_text(body_text)
    has_phone = _has_link(soup, r"^tel:") or has_phone_in_text(body_text)
    out.add_binary("contact", "process", has_mail or has_phone)

    has_whatsapp = _has_link(soup, r"wa\.me|whatsapp") or "whatsapp" in text
    out.add_binary("whatsapp", "process", has_whatsapp, otherwise="partial")

    form = soup.find("form")
    if form is None:
        out.add("form", "process", "pass", "form_pass_none")
    else:
        required = len(form.find_all(["input", "textarea"], required=True))
        if required <= MAX_EASY_FORM_FIELDS:
            out.add("form", "process", "pass", "form_pass", n=required)
        elif required <= MAX_OK_FORM_FIELDS:
            out.add("form", "process", "partial", "form_partial", n=required)
        else:
            out.add("form", "process", "fail", "form_fail", n=required)

    out.add_binary("cta", "process", contains_any(text, CTA_WORDS))


def _check_benefits(text: str, out: _Collector) -> None:
    out.add_binary("salary", "benefits", contains_any(text, SALARY_WORDS))
    out.add_binary("training", "benefits", contains_any(text, TRAINING_WORDS))
    out.add_binary("team", "benefits", contains_any(text, TEAM_WORDS))
    out.add_binary("extras", "benefits", contains_any(text, EXTRAS_WORDS), otherwise="partial")


def _check_reach(soup: BeautifulSoup, text: str, out: _Collector) -> None:
    out.add_binary("mobile", "reach", soup.find("meta", attrs={"name": "viewport"}) is not None)

    direct_address = sum(text.count(word) for word in DIRECT_ADDRESS_WORDS)
    out.add_binary("tone", "reach", direct_address >= MIN_DIRECT_ADDRESS_HITS, otherwise="partial")

    images = len(soup.find_all("img"))
    if images:
        out.add("images", "reach", "pass", "images_pass", n=images)
    else:
        out.add("images", "reach", "fail", "images_fail")

    og_tags = soup.find_all("meta", attrs={"property": re.compile("^og:")})
    out.add_binary("shareable", "reach", len(og_tags) >= MIN_OPEN_GRAPH_TAGS)


def _aggregate(checks: list[Check], url: str, lang: Lang, load_time: float) -> Report:
    categories: dict[str, CategoryScore] = {}
    for key in CATEGORY_KEYS:
        name = CATEGORIES[lang][key]
        in_category = [check for check in checks if check.category == name]
        passed = sum(check.status == "pass" for check in in_category)
        total = len(in_category)
        score = round(passed / total * 100) if total else 0
        categories[name] = CategoryScore(score=score, passed=passed, total=total)

    overall = round(sum(c.score for c in categories.values()) / len(categories))
    return Report(
        url=url,
        overall=overall,
        categories=categories,
        checks=checks,
        total_passed=sum(c.passed for c in categories.values()),
        total_checks=sum(c.total for c in categories.values()),
        load_time=round(load_time, 2),
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def count_words(text: str) -> int:
    return len(text.split())


def contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def page_title(soup: BeautifulSoup) -> str:
    if soup.title is None or soup.title.string is None:
        return ""
    return str(soup.title.string).strip()


def has_phone_in_text(text: str) -> bool:
    for match in PHONE_TEXT_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 9 <= len(digits) <= 13:
            return True
    return False


def has_email_in_text(text: str) -> bool:
    return EMAIL_TEXT_RE.search(text) is not None


def _has_link(soup: BeautifulSoup, href_pattern: str) -> bool:
    return soup.find("a", href=re.compile(href_pattern, re.IGNORECASE)) is not None
