"""Localized texts for the job-ad check (German, French, English).

All user-facing strings live here so the analysis code stays language-agnostic.
Finding texts are ``str.format`` templates; the analysis fills in values such as
``{n}`` (a count) or ``{title}`` (the page title).
"""

from __future__ import annotations

from typing import Final, Literal, get_args

Lang = Literal["de", "fr", "en"]
SUPPORTED_LANGS: Final[tuple[Lang, ...]] = get_args(Lang)
DEFAULT_LANG: Final[Lang] = "de"


def resolve_lang(value: object) -> Lang:
    """Returns a supported language code, falling back to German."""
    if isinstance(value, str) and value in SUPPORTED_LANGS:
        return value
    return DEFAULT_LANG


CATEGORY_KEYS: Final = ("task", "process", "benefits", "reach")

CATEGORIES: Final[dict[Lang, dict[str, str]]] = {
    "de": {
        "task": "Aufgabenbeschreibung",
        "process": "Bewerbungsprozess",
        "benefits": "Arbeitgebervorteile",
        "reach": "Reichweite",
    },
    "fr": {
        "task": "Description du poste",
        "process": "Processus de candidature",
        "benefits": "Avantages employeur",
        "reach": "Portée",
    },
    "en": {
        "task": "Role description",
        "process": "Application process",
        "benefits": "Employer benefits",
        "reach": "Reach",
    },
}

CHECK_NAMES: Final[dict[str, dict[Lang, str]]] = {
    "text_length": {"de": "Textlänge", "fr": "Longueur du texte", "en": "Text length"},
    "concrete": {
        "de": "Konkrete Angaben",
        "fr": "Informations concrètes",
        "en": "Concrete details",
    },
    "structure": {"de": "Struktur", "fr": "Structure", "en": "Structure"},
    "title": {"de": "Aussagekräftiger Titel", "fr": "Titre parlant", "en": "Meaningful title"},
    "contact": {
        "de": "Direkter Kontakt sichtbar",
        "fr": "Contact direct visible",
        "en": "Direct contact visible",
    },
    "whatsapp": {"de": "WhatsApp-Option", "fr": "Option WhatsApp", "en": "WhatsApp option"},
    "form": {
        "de": "Bewerbungsformular",
        "fr": "Formulaire de candidature",
        "en": "Application form",
    },
    "cta": {
        "de": "Klarer Aufruf zur Bewerbung",
        "fr": "Appel clair à candidater",
        "en": "Clear call to apply",
    },
    "salary": {"de": "Lohn erwähnt", "fr": "Salaire mentionné", "en": "Salary mentioned"},
    "training": {
        "de": "Weiterbildung erwähnt",
        "fr": "Formation continue mentionnée",
        "en": "Training mentioned",
    },
    "team": {
        "de": "Team/Arbeitsklima erwähnt",
        "fr": "Équipe/ambiance mentionnée",
        "en": "Team/culture mentioned",
    },
    "extras": {
        "de": "Zusatzleistungen erwähnt",
        "fr": "Avantages additionnels mentionnés",
        "en": "Extra benefits mentioned",
    },
    "mobile": {"de": "Mobil optimiert", "fr": "Optimisé mobile", "en": "Mobile optimized"},
    "tone": {"de": "Persönliche Ansprache", "fr": "Ton personnel", "en": "Personal tone"},
    "images": {"de": "Bildmaterial vorhanden", "fr": "Photos présentes", "en": "Images present"},
    "shareable": {
        "de": "Teilbar auf Social Media",
        "fr": "Partageable sur les réseaux",
        "en": "Shareable on social media",
    },
}

FINDINGS: Final[dict[Lang, dict[str, str]]] = {
    "de": {
        "text_length_pass": "{n} Wörter, guter Umfang für echte Details",
        "text_length_fail": "Nur {n} Wörter, vermutlich zu wenig Substanz",
        "text_length_partial": "{n} Wörter, könnte für Bewerbende lang wirken",
        "concrete_pass": "Pensum/Ausbildung konkret genannt",
        "concrete_fail": "Keine konkreten Angaben zu Pensum oder Ausbildung gefunden",
        "structure_pass": "{n} Listenpunkte gefunden",
        "structure_partial": "{n} Listenpunkt gefunden, könnte mehr Struktur vertragen",
        "structure_fail": "Kein strukturierter Aufbau (Listen/Absätze) erkennbar",
        "title_pass": "„{title}“",
        "title_fail": "Kein aussagekräftiger Titel gefunden",
        "contact_pass": "E-Mail oder Telefonlink vorhanden",
        "contact_fail": "Keine direkte Kontaktmöglichkeit (E-Mail/Telefon) gefunden",
        "whatsapp_pass": "WhatsApp-Kontakt gefunden",
        "whatsapp_partial": "Kein WhatsApp-Kontakt, gerade im Handwerk oft der einfachste Weg",
        "form_pass_none": "Kein aufwendiges Formular, Kontakt direkt möglich",
        "form_pass": "{n} Pflichtfelder im Formular, überschaubar",
        "form_partial": "{n} Pflichtfelder im Formular",
        "form_fail": "{n} Pflichtfelder im Formular, das schreckt eher ab",
        "cta_pass": "Klare Aufforderung zur Bewerbung gefunden",
        "cta_fail": "Keine klare Aufforderung zur Bewerbung gefunden",
        "salary_pass": "Lohn/Gehalt wird erwähnt",
        "salary_fail": "Kein Hinweis auf Lohn oder Gehalt",
        "training_pass": "Weiterbildung/Entwicklung wird erwähnt",
        "training_fail": "Keine Weiterbildungsmöglichkeiten erwähnt",
        "team_pass": "Team oder Arbeitsklima wird beschrieben",
        "team_fail": "Nichts zu Team oder Arbeitsklima gefunden",
        "extras_pass": "Zusatzleistungen (Ferien, Bonus, Fahrzeug o. Ä.) genannt",
        "extras_partial": "Keine Zusatzleistungen genannt",
        "mobile_pass": "Mobilfreundlich, viele Fachkräfte suchen auf dem Handy",
        "mobile_fail": "Keine mobile Optimierung erkennbar",
        "tone_pass": "Direkte, persönliche Ansprache erkennbar",
        "tone_partial": "Wirkt eher unpersönlich formuliert",
        "images_pass": "{n} Bild(er) auf der Seite",
        "images_fail": "Kein Bildmaterial gefunden, Fotos schaffen Vertrauen",
        "shareable_pass": "Vorschaubild/-text beim Teilen vorhanden",
        "shareable_fail": "Kein Vorschaubild beim Teilen (WhatsApp/Social Media)",
    },
    "fr": {
        "text_length_pass": "{n} mots, bon volume pour de vrais détails",
        "text_length_fail": "Seulement {n} mots, probablement trop peu de contenu",
        "text_length_partial": "{n} mots, pourrait sembler long aux candidats",
        "concrete_pass": "Taux d'activité/formation indiqués concrètement",
        "concrete_fail": "Aucune indication concrète sur le taux d'activité ou la formation",
        "structure_pass": "{n} éléments de liste trouvés",
        "structure_partial": "{n} élément de liste trouvé, pourrait être mieux structuré",
        "structure_fail": "Aucune structure claire (listes/paragraphes) reconnaissable",
        "title_pass": "« {title} »",
        "title_fail": "Aucun titre parlant trouvé",
        "contact_pass": "Lien e-mail ou téléphone présent",
        "contact_fail": "Aucun moyen de contact direct (e-mail/téléphone) trouvé",
        "whatsapp_pass": "Contact WhatsApp trouvé",
        "whatsapp_partial": (
            "Pas de contact WhatsApp, souvent le moyen le plus simple dans l'artisanat"
        ),
        "form_pass_none": "Pas de formulaire complexe, contact direct possible",
        "form_pass": "{n} champs obligatoires, raisonnable",
        "form_partial": "{n} champs obligatoires dans le formulaire",
        "form_fail": "{n} champs obligatoires, cela peut décourager",
        "cta_pass": "Appel clair à candidater trouvé",
        "cta_fail": "Aucun appel clair à candidater trouvé",
        "salary_pass": "Le salaire est mentionné",
        "salary_fail": "Aucune indication de salaire",
        "training_pass": "Formation continue/développement mentionné",
        "training_fail": "Aucune possibilité de formation continue mentionnée",
        "team_pass": "L'équipe ou l'ambiance de travail est décrite",
        "team_fail": "Rien sur l'équipe ou l'ambiance de travail",
        "extras_pass": "Avantages additionnels mentionnés (vacances, bonus, véhicule, etc.)",
        "extras_partial": "Aucun avantage additionnel mentionné",
        "mobile_pass": "Adapté mobile, beaucoup de spécialistes cherchent sur leur téléphone",
        "mobile_fail": "Aucune optimisation mobile reconnaissable",
        "tone_pass": "Ton direct et personnel reconnaissable",
        "tone_partial": "Formulation plutôt impersonnelle",
        "images_pass": "{n} image(s) sur la page",
        "images_fail": "Aucune image trouvée, les photos créent de la confiance",
        "shareable_pass": "Image/texte d'aperçu présents lors du partage",
        "shareable_fail": "Pas d'aperçu lors du partage (WhatsApp/réseaux sociaux)",
    },
    "en": {
        "text_length_pass": "{n} words, good amount of real detail",
        "text_length_fail": "Only {n} words, likely too little substance",
        "text_length_partial": "{n} words, might feel long to applicants",
        "concrete_pass": "Workload/qualification stated concretely",
        "concrete_fail": "No concrete details on workload or qualification found",
        "structure_pass": "{n} list items found",
        "structure_partial": "{n} list item found, could use more structure",
        "structure_fail": "No clear structure (lists/paragraphs) recognizable",
        "title_pass": "“{title}”",
        "title_fail": "No meaningful title found",
        "contact_pass": "Email or phone link present",
        "contact_fail": "No direct contact option (email/phone) found",
        "whatsapp_pass": "WhatsApp contact found",
        "whatsapp_partial": "No WhatsApp contact, often the easiest option in the trades",
        "form_pass_none": "No lengthy form, direct contact possible",
        "form_pass": "{n} required fields, reasonable",
        "form_partial": "{n} required fields in the form",
        "form_fail": "{n} required fields, likely to discourage applicants",
        "cta_pass": "Clear call to apply found",
        "cta_fail": "No clear call to apply found",
        "salary_pass": "Salary is mentioned",
        "salary_fail": "No mention of salary",
        "training_pass": "Training/development is mentioned",
        "training_fail": "No training opportunities mentioned",
        "team_pass": "Team or work culture is described",
        "team_fail": "Nothing about team or work culture found",
        "extras_pass": "Extra benefits mentioned (vacation, bonus, vehicle, etc.)",
        "extras_partial": "No extra benefits mentioned",
        "mobile_pass": "Mobile-friendly, many tradespeople search on their phone",
        "mobile_fail": "No mobile optimization recognizable",
        "tone_pass": "Direct, personal tone recognizable",
        "tone_partial": "Reads fairly impersonal",
        "images_pass": "{n} image(s) on the page",
        "images_fail": "No images found, photos build trust",
        "shareable_pass": "Preview image/text present when shared",
        "shareable_fail": "No preview when shared (WhatsApp/social media)",
    },
}

ERRORS: Final[dict[Lang, dict[str, str]]] = {
    "de": {
        "invalid_url": "Ungültige URL",
        "blocked_url": "Diese Adresse kann aus Sicherheitsgründen nicht geprüft werden",
        "unreachable": "Stellenanzeige nicht erreichbar ({reason})",
        "missing_url": "Keine URL angegeben",
        "invalid_email": "Ungültige E-Mail-Adresse",
        "not_configured": (
            "Der E-Mail-Versand ist gerade nicht verfügbar. Bitte später erneut versuchen."
        ),
        "send_failed": "Der Versand hat leider nicht geklappt. Bitte später erneut versuchen.",
        "rate_limited": "Zu viele Anfragen. Bitte in einer Minute erneut versuchen.",
    },
    "fr": {
        "invalid_url": "URL invalide",
        "blocked_url": "Cette adresse ne peut pas être vérifiée pour des raisons de sécurité",
        "unreachable": "Annonce inaccessible ({reason})",
        "missing_url": "Aucune URL indiquée",
        "invalid_email": "Adresse e-mail invalide",
        "not_configured": (
            "L'envoi par e-mail n'est pas disponible pour le moment. Merci de réessayer plus tard."
        ),
        "send_failed": "L'envoi a malheureusement échoué. Merci de réessayer plus tard.",
        "rate_limited": "Trop de requêtes. Merci de réessayer dans une minute.",
    },
    "en": {
        "invalid_url": "Invalid URL",
        "blocked_url": "This address cannot be checked for security reasons",
        "unreachable": "Job ad unreachable ({reason})",
        "missing_url": "No URL provided",
        "invalid_email": "Invalid email address",
        "not_configured": "Email sending is currently unavailable. Please try again later.",
        "send_failed": "Sending failed. Please try again later.",
        "rate_limited": "Too many requests. Please try again in a minute.",
    },
}

EMAIL_TEXTS: Final[dict[Lang, dict[str, str]]] = {
    "de": {
        "overall": "Gesamtscore",
        "subject": "Ihr Stellenanzeigen-Check-Ergebnis · A Match",
        "intro": "Hier Ihr Stellenanzeigen-Check-Ergebnis von A Match:",
        "findings_title": "Erste Ansatzpunkte",
        "all_good": "Starke Anzeige, alle Punkte erfüllt!",
        "cta_btn": "Kostenloses Erstgespräch buchen",
    },
    "fr": {
        "overall": "Score global",
        "subject": "Votre résultat de vérification d'annonce · A Match",
        "intro": "Voici votre résultat de vérification d'annonce A Match :",
        "findings_title": "Premières pistes",
        "all_good": "Annonce solide, tous les points sont remplis !",
        "cta_btn": "Réserver un entretien initial gratuit",
    },
    "en": {
        "overall": "Overall score",
        "subject": "Your Job Ad Check Result · A Match",
        "intro": "Here is your A Match job ad check result:",
        "findings_title": "First pointers",
        "all_good": "Strong job ad, every point is covered!",
        "cta_btn": "Book a free initial consultation",
    },
}

BOOKING_URLS: Final[dict[Lang, str]] = {
    "de": "https://amatch.ch/termin.html",
    "fr": "https://amatch.ch/fr/rendez-vous.html",
    "en": "https://amatch.ch/en/book-a-call.html",
}
