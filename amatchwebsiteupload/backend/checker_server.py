#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A Match — Stellenanzeigen-Check backend.

Real, automated ~30-second audit of a job-ad URL — NOT a technical SEO/
performance scan. It fetches the page server-side (no CORS issue, since
this runs server-to-server) and evaluates content signals that actually
matter for trades recruiting, grouped into the same four categories shown
in the "Was wir prüfen" section on the page: Aufgabenbeschreibung (task
description), Bewerbungsprozess (application process), Arbeitgebervorteile
(employer benefits) and Reichweite (reach / audience fit). Each category
gets a 0-100 score from simple, explainable checks — deliberately not a
line-by-line technical report, just enough for an owner to see where their
ad is weak and act on it. Rule-based (keyword/structure detection), not an
AI judgement of writing quality — reported honestly as "first pointers".

Pass ?lang=de|fr|en to localize check names/findings (default: de).

Run: python3 checker_server.py   (listens on :8913)
Requires: flask, requests, beautifulsoup4 (pip install flask requests beautifulsoup4)
"""
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

app = Flask(__name__)
UA = "Mozilla/5.0 (compatible; AMatchStellenanzeigenCheck/1.0; +https://amatch.ch)"

BENEFIT_WORDS = {
    "salary": ["lohn", "gehalt", "salär", "chf", "fr.", "salary", "salaire"],
    "training": ["weiterbildung", "kurse", "weiterentwicklung", "perspektive", "aufstieg", "training", "formation"],
    "team": ["team", "kolleg", "kultur", "zusammenarbeit", "familiär", "atmosphäre", "équipe"],
    "extras": ["ferien", "urlaub", "bonus", "13.", "firmenfahrzeug", "pensionskasse", "flexibel", "flexible", "vacances"],
}
CONCRETE_PATTERNS = [r"\b\d{1,3}\s?%", r"\befz\b", r"\bcfc\b", r"\blehre\b", r"\bausbildung\b", r"\bpensum\b",
                     r"\bvollzeit\b", r"\bteilzeit\b", r"\bfull.?time\b", r"\bpart.?time\b"]
CTA_WORDS = ["bewerben", "bewerbung", "kontakt", "melden sie sich", "melde dich", "jetzt bewerben",
             "apply", "contact us", "postuler", "candidature", "contactez"]
INFORMAL_WORDS = [" sie ", " ihr", " ihre", " du ", " dein", " deine", " your ", " you ", " vous ", " votre"]

# Contact info is very often printed as plain text (e.g. "Telefon 031 859 77 77")
# rather than wrapped in a mailto:/tel: link, so the "direct contact" check must
# also scan the visible text, not just <a href> attributes. Covers Swiss local
# numbers (0XX XXX XX XX) and international ones (+41 / 0041), with any mix of
# spaces, dots or hyphens as separators.
PHONE_TEXT_RE = re.compile(
    r"(?:\+41|0041)[\s.\-]?\(?0?\)?[\s.\-]?\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}"
    r"|0\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2}[\s.\-]?\d{2}"
)
EMAIL_TEXT_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def has_phone_in_text(text):
    for m in PHONE_TEXT_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 9 <= len(digits) <= 13:
            return True
    return False


def has_email_in_text(text):
    return bool(EMAIL_TEXT_RE.search(text))

# ── Localized labels ──────────────────────────────────────────────────────
NAMES = {
    "text_length": {"de": "Textlänge", "fr": "Longueur du texte", "en": "Text length"},
    "concrete": {"de": "Konkrete Angaben", "fr": "Informations concrètes", "en": "Concrete details"},
    "structure": {"de": "Struktur", "fr": "Structure", "en": "Structure"},
    "title": {"de": "Aussagekräftiger Titel", "fr": "Titre parlant", "en": "Meaningful title"},
    "contact": {"de": "Direkter Kontakt sichtbar", "fr": "Contact direct visible", "en": "Direct contact visible"},
    "whatsapp": {"de": "WhatsApp-Option", "fr": "Option WhatsApp", "en": "WhatsApp option"},
    "form": {"de": "Bewerbungsformular", "fr": "Formulaire de candidature", "en": "Application form"},
    "cta": {"de": "Klarer Aufruf zur Bewerbung", "fr": "Appel clair à candidater", "en": "Clear call to apply"},
    "salary": {"de": "Lohn erwähnt", "fr": "Salaire mentionné", "en": "Salary mentioned"},
    "training": {"de": "Weiterbildung erwähnt", "fr": "Formation continue mentionnée", "en": "Training mentioned"},
    "team": {"de": "Team/Arbeitsklima erwähnt", "fr": "Équipe/ambiance mentionnée", "en": "Team/culture mentioned"},
    "extras": {"de": "Zusatzleistungen erwähnt", "fr": "Avantages additionnels mentionnés", "en": "Extra benefits mentioned"},
    "mobile": {"de": "Mobil optimiert", "fr": "Optimisé mobile", "en": "Mobile optimized"},
    "tone": {"de": "Persönliche Ansprache", "fr": "Ton personnel", "en": "Personal tone"},
    "images": {"de": "Bildmaterial vorhanden", "fr": "Photos présentes", "en": "Images present"},
    "shareable": {"de": "Teilbar auf Social Media", "fr": "Partageable sur les réseaux", "en": "Shareable on social media"},
}
CATS = {
    "de": {"task": "Aufgabenbeschreibung", "process": "Bewerbungsprozess", "benefits": "Arbeitgebervorteile", "reach": "Reichweite"},
    "fr": {"task": "Description du poste", "process": "Processus de candidature", "benefits": "Avantages employeur", "reach": "Portée"},
    "en": {"task": "Role description", "process": "Application process", "benefits": "Employer benefits", "reach": "Reach"},
}
FINDINGS = {
    "de": {
        "text_length_pass": lambda n: f"{n} Wörter, guter Umfang für echte Details",
        "text_length_fail": lambda n: f"Nur {n} Wörter, vermutlich zu wenig Substanz",
        "text_length_partial": lambda n: f"{n} Wörter, könnte für Bewerbende lang wirken",
        "concrete_pass": lambda: "Pensum/Ausbildung konkret genannt",
        "concrete_fail": lambda: "Keine konkreten Angaben zu Pensum oder Ausbildung gefunden",
        "structure_pass": lambda n: f"{n} Listenpunkte gefunden",
        "structure_partial": lambda n: f"{n} Listenpunkt gefunden, könnte mehr Struktur vertragen",
        "structure_fail": lambda n: "Kein strukturierter Aufbau (Listen/Absätze) erkennbar",
        "title_pass": lambda t: f"„{t}“",
        "title_fail": lambda t: "Kein aussagekräftiger Titel gefunden",
        "contact_pass": lambda: "E-Mail oder Telefonlink vorhanden",
        "contact_fail": lambda: "Keine direkte Kontaktmöglichkeit (E-Mail/Telefon) gefunden",
        "whatsapp_pass": lambda: "WhatsApp-Kontakt gefunden",
        "whatsapp_partial": lambda: "Kein WhatsApp-Kontakt, gerade im Handwerk oft der einfachste Weg",
        "form_pass_none": lambda: "Kein aufwendiges Formular, Kontakt direkt möglich",
        "form_pass": lambda n: f"{n} Pflichtfelder im Formular, überschaubar",
        "form_partial": lambda n: f"{n} Pflichtfelder im Formular",
        "form_fail": lambda n: f"{n} Pflichtfelder im Formular, das schreckt eher ab",
        "cta_pass": lambda: "Klare Aufforderung zur Bewerbung gefunden",
        "cta_fail": lambda: "Keine klare Aufforderung zur Bewerbung gefunden",
        "salary_pass": lambda: "Lohn/Gehalt wird erwähnt",
        "salary_fail": lambda: "Kein Hinweis auf Lohn oder Gehalt",
        "training_pass": lambda: "Weiterbildung/Entwicklung wird erwähnt",
        "training_fail": lambda: "Keine Weiterbildungsmöglichkeiten erwähnt",
        "team_pass": lambda: "Team oder Arbeitsklima wird beschrieben",
        "team_fail": lambda: "Nichts zu Team oder Arbeitsklima gefunden",
        "extras_pass": lambda: "Zusatzleistungen (Ferien, Bonus, Fahrzeug o. Ä.) genannt",
        "extras_partial": lambda: "Keine Zusatzleistungen genannt",
        "mobile_pass": lambda: "Mobilfreundlich, viele Fachkräfte suchen auf dem Handy",
        "mobile_fail": lambda: "Keine mobile Optimierung erkennbar",
        "tone_pass": lambda: "Direkte, persönliche Ansprache erkennbar",
        "tone_partial": lambda: "Wirkt eher unpersönlich formuliert",
        "images_pass": lambda n: f"{n} Bild(er) auf der Seite",
        "images_fail": lambda: "Kein Bildmaterial gefunden, Fotos schaffen Vertrauen",
        "shareable_pass": lambda: "Vorschaubild/-text beim Teilen vorhanden",
        "shareable_fail": lambda: "Kein Vorschaubild beim Teilen (WhatsApp/Social Media)",
    },
    "fr": {
        "text_length_pass": lambda n: f"{n} mots, bon volume pour de vrais détails",
        "text_length_fail": lambda n: f"Seulement {n} mots, probablement trop peu de contenu",
        "text_length_partial": lambda n: f"{n} mots, pourrait sembler long aux candidats",
        "concrete_pass": lambda: "Taux d'activité/formation indiqués concrètement",
        "concrete_fail": lambda: "Aucune indication concrète sur le taux d'activité ou la formation",
        "structure_pass": lambda n: f"{n} éléments de liste trouvés",
        "structure_partial": lambda n: f"{n} élément de liste trouvé, pourrait être mieux structuré",
        "structure_fail": lambda n: "Aucune structure claire (listes/paragraphes) reconnaissable",
        "title_pass": lambda t: f"« {t} »",
        "title_fail": lambda t: "Aucun titre parlant trouvé",
        "contact_pass": lambda: "Lien e-mail ou téléphone présent",
        "contact_fail": lambda: "Aucun moyen de contact direct (e-mail/téléphone) trouvé",
        "whatsapp_pass": lambda: "Contact WhatsApp trouvé",
        "whatsapp_partial": lambda: "Pas de contact WhatsApp, souvent le moyen le plus simple dans l'artisanat",
        "form_pass_none": lambda: "Pas de formulaire complexe, contact direct possible",
        "form_pass": lambda n: f"{n} champs obligatoires, raisonnable",
        "form_partial": lambda n: f"{n} champs obligatoires dans le formulaire",
        "form_fail": lambda n: f"{n} champs obligatoires, cela peut décourager",
        "cta_pass": lambda: "Appel clair à candidater trouvé",
        "cta_fail": lambda: "Aucun appel clair à candidater trouvé",
        "salary_pass": lambda: "Le salaire est mentionné",
        "salary_fail": lambda: "Aucune indication de salaire",
        "training_pass": lambda: "Formation continue/développement mentionné",
        "training_fail": lambda: "Aucune possibilité de formation continue mentionnée",
        "team_pass": lambda: "L'équipe ou l'ambiance de travail est décrite",
        "team_fail": lambda: "Rien sur l'équipe ou l'ambiance de travail",
        "extras_pass": lambda: "Avantages additionnels mentionnés (vacances, bonus, véhicule, etc.)",
        "extras_partial": lambda: "Aucun avantage additionnel mentionné",
        "mobile_pass": lambda: "Adapté mobile, beaucoup de spécialistes cherchent sur leur téléphone",
        "mobile_fail": lambda: "Aucune optimisation mobile reconnaissable",
        "tone_pass": lambda: "Ton direct et personnel reconnaissable",
        "tone_partial": lambda: "Formulation plutôt impersonnelle",
        "images_pass": lambda n: f"{n} image(s) sur la page",
        "images_fail": lambda: "Aucune image trouvée, les photos créent de la confiance",
        "shareable_pass": lambda: "Image/texte d'aperçu présents lors du partage",
        "shareable_fail": lambda: "Pas d'aperçu lors du partage (WhatsApp/réseaux sociaux)",
    },
    "en": {
        "text_length_pass": lambda n: f"{n} words, good amount of real detail",
        "text_length_fail": lambda n: f"Only {n} words, likely too little substance",
        "text_length_partial": lambda n: f"{n} words, might feel long to applicants",
        "concrete_pass": lambda: "Workload/qualification stated concretely",
        "concrete_fail": lambda: "No concrete details on workload or qualification found",
        "structure_pass": lambda n: f"{n} list items found",
        "structure_partial": lambda n: f"{n} list item found, could use more structure",
        "structure_fail": lambda n: "No clear structure (lists/paragraphs) recognizable",
        "title_pass": lambda t: f"“{t}”",
        "title_fail": lambda t: "No meaningful title found",
        "contact_pass": lambda: "Email or phone link present",
        "contact_fail": lambda: "No direct contact option (email/phone) found",
        "whatsapp_pass": lambda: "WhatsApp contact found",
        "whatsapp_partial": lambda: "No WhatsApp contact, often the easiest option in the trades",
        "form_pass_none": lambda: "No lengthy form, direct contact possible",
        "form_pass": lambda n: f"{n} required fields, reasonable",
        "form_partial": lambda n: f"{n} required fields in the form",
        "form_fail": lambda n: f"{n} required fields, likely to discourage applicants",
        "cta_pass": lambda: "Clear call to apply found",
        "cta_fail": lambda: "No clear call to apply found",
        "salary_pass": lambda: "Salary is mentioned",
        "salary_fail": lambda: "No mention of salary",
        "training_pass": lambda: "Training/development is mentioned",
        "training_fail": lambda: "No training opportunities mentioned",
        "team_pass": lambda: "Team or work culture is described",
        "team_fail": lambda: "Nothing about team or work culture found",
        "extras_pass": lambda: "Extra benefits mentioned (vacation, bonus, vehicle, etc.)",
        "extras_partial": lambda: "No extra benefits mentioned",
        "mobile_pass": lambda: "Mobile-friendly, many tradespeople search on their phone",
        "mobile_fail": lambda: "No mobile optimization recognizable",
        "tone_pass": lambda: "Direct, personal tone recognizable",
        "tone_partial": lambda: "Reads fairly impersonal",
        "images_pass": lambda n: f"{n} image(s) on the page",
        "images_fail": lambda: "No images found, photos build trust",
        "shareable_pass": lambda: "Preview image/text present when shared",
        "shareable_fail": lambda: "No preview when shared (WhatsApp/social media)",
    },
}


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def normalize_url(u):
    u = u.strip()
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


def fetch(url, timeout=8):
    return requests.get(url, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True)


def count_words(text):
    return len(re.findall(r"[^\s]+", text))


def any_keyword(text_lower, words):
    return any(w in text_lower for w in words)


def check_job_ad(raw_url, lang):
    if lang not in ("de", "fr", "en"):
        lang = "de"
    url = normalize_url(raw_url)
    parsed = urlparse(url)
    if not parsed.netloc:
        return {"error": "Ungültige URL" if lang == "de" else ("URL invalide" if lang == "fr" else "Invalid URL")}

    t0 = time.time()
    try:
        resp = fetch(url)
    except requests.exceptions.RequestException as e:
        msg = {"de": f"Stellenanzeige nicht erreichbar ({e.__class__.__name__})",
               "fr": f"Annonce inaccessible ({e.__class__.__name__})",
               "en": f"Job ad unreachable ({e.__class__.__name__})"}[lang]
        return {"error": msg}
    load_time = time.time() - t0

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(" ", strip=True)
    text_lower = " " + body_text.lower() + " "
    word_count = count_words(body_text)

    F = FINDINGS[lang]
    cat = CATS[lang]
    checks = []

    def add(key, cat_name, status, finding_key, *args):
        checks.append({"category": cat_name, "name": NAMES[key][lang], "status": status, "finding": F[finding_key](*args)})

    # ── Task description ─────────────────────────────────────────────
    if 150 <= word_count <= 700:
        add("text_length", cat["task"], "pass", "text_length_pass", word_count)
    elif word_count < 150:
        add("text_length", cat["task"], "fail", "text_length_fail", word_count)
    else:
        add("text_length", cat["task"], "partial", "text_length_partial", word_count)

    has_concrete = any(re.search(p, text_lower) for p in CONCRETE_PATTERNS)
    add("concrete", cat["task"], "pass" if has_concrete else "fail", "concrete_pass" if has_concrete else "concrete_fail")

    list_items = len(soup.find_all("li"))
    if list_items >= 3:
        add("structure", cat["task"], "pass", "structure_pass", list_items)
    elif list_items >= 1:
        add("structure", cat["task"], "partial", "structure_partial", list_items)
    else:
        add("structure", cat["task"], "fail", "structure_fail", list_items)

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    add("title", cat["task"], "pass" if len(title) >= 12 else "fail",
        "title_pass" if len(title) >= 12 else "title_fail", title)

    # ── Application process ──────────────────────────────────────────
    has_mail = bool(soup.find("a", href=re.compile("^mailto:", re.I))) or has_email_in_text(body_text)
    has_tel = bool(soup.find("a", href=re.compile("^tel:", re.I))) or has_phone_in_text(body_text)
    add("contact", cat["process"], "pass" if (has_mail or has_tel) else "fail",
        "contact_pass" if (has_mail or has_tel) else "contact_fail")

    has_whatsapp = bool(soup.find("a", href=re.compile(r"wa\.me|whatsapp", re.I))) or "whatsapp" in text_lower
    add("whatsapp", cat["process"], "pass" if has_whatsapp else "partial",
        "whatsapp_pass" if has_whatsapp else "whatsapp_partial")

    forms = soup.find_all("form")
    if forms:
        required_fields = len(forms[0].find_all(["input", "textarea"], required=True))
        if required_fields <= 4:
            add("form", cat["process"], "pass", "form_pass", required_fields)
        elif required_fields <= 7:
            add("form", cat["process"], "partial", "form_partial", required_fields)
        else:
            add("form", cat["process"], "fail", "form_fail", required_fields)
    else:
        add("form", cat["process"], "pass", "form_pass_none")

    has_cta = any_keyword(text_lower, CTA_WORDS)
    add("cta", cat["process"], "pass" if has_cta else "fail", "cta_pass" if has_cta else "cta_fail")

    # ── Employer benefits ────────────────────────────────────────────
    has_salary = any_keyword(text_lower, BENEFIT_WORDS["salary"])
    add("salary", cat["benefits"], "pass" if has_salary else "fail", "salary_pass" if has_salary else "salary_fail")

    has_training = any_keyword(text_lower, BENEFIT_WORDS["training"])
    add("training", cat["benefits"], "pass" if has_training else "fail", "training_pass" if has_training else "training_fail")

    has_team = any_keyword(text_lower, BENEFIT_WORDS["team"])
    add("team", cat["benefits"], "pass" if has_team else "fail", "team_pass" if has_team else "team_fail")

    has_extras = any_keyword(text_lower, BENEFIT_WORDS["extras"])
    add("extras", cat["benefits"], "pass" if has_extras else "partial", "extras_pass" if has_extras else "extras_partial")

    # ── Reach ─────────────────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": "viewport"})
    add("mobile", cat["reach"], "pass" if viewport else "fail", "mobile_pass" if viewport else "mobile_fail")

    informal_hits = sum(text_lower.count(w) for w in INFORMAL_WORDS)
    add("tone", cat["reach"], "pass" if informal_hits >= 3 else "partial", "tone_pass" if informal_hits >= 3 else "tone_partial")

    imgs = soup.find_all("img")
    if imgs:
        add("images", cat["reach"], "pass", "images_pass", len(imgs))
    else:
        add("images", cat["reach"], "fail", "images_fail")

    og_tags = soup.find_all("meta", attrs={"property": re.compile("^og:")})
    add("shareable", cat["reach"], "pass" if len(og_tags) >= 2 else "fail",
        "shareable_pass" if len(og_tags) >= 2 else "shareable_fail")

    # ── Aggregate ───────────────────────────────────────────────────
    categories = {}
    for cat_name in cat.values():
        cat_checks = [c for c in checks if c["category"] == cat_name]
        passed = len([c for c in cat_checks if c["status"] == "pass"])
        total = len(cat_checks)
        categories[cat_name] = {"score": round(passed / total * 100) if total else 0, "passed": passed, "total": total}

    overall = round(sum(c["score"] for c in categories.values()) / len(categories))
    total_passed = sum(c["passed"] for c in categories.values())
    total_checks = sum(c["total"] for c in categories.values())

    return {
        "url": url,
        "overall": overall,
        "categories": categories,
        "checks": checks,
        "total_passed": total_passed,
        "total_checks": total_checks,
        "load_time": round(load_time, 2),
    }


@app.route("/api/check", methods=["GET", "OPTIONS"])
def api_check():
    if request.method == "OPTIONS":
        return ("", 204)
    url = request.args.get("url", "")
    lang = request.args.get("lang", "de")
    if not url:
        return jsonify({"error": "Keine URL angegeben"}), 400
    result = check_job_ad(url, lang)
    if "error" in result:
        return jsonify(result), 502
    return jsonify(result)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8913, debug=False)
