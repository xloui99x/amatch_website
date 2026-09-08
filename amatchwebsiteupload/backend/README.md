# A Match — Stellenanzeigen-Check Backend

Macht den "Stellenanzeige analysieren"-Button auf `stellencheck.html` /
`fr/verification-annonce.html` / `en/job-ad-check.html` echt: er ruft die
eingegebene URL serverseitig auf (kein CORS-Problem, da Server-zu-Server)
und bewertet **Inhalt**, nicht Technik — bewusst **keine SEO-/Performance-
Metriken**. Geprüft wird, ob die Stellenanzeige als Text wirklich gut ist
und die richtige Zielgruppe anspricht, in denselben vier Kategorien wie im
"Was wir prüfen"-Abschnitt: Aufgabenbeschreibung, Bewerbungsprozess,
Arbeitgebervorteile, Reichweite (z. B. Textlänge und Konkretheit der
Aufgabenbeschreibung, sichtbarer Kontaktweg, erwähnter Lohn/Weiterbildung/
Team, mobile Optimierung, persönliche Ansprache, Bildmaterial).

Das ist eine **regelbasierte** Auswertung (Stichwort-/Struktur-Erkennung),
keine KI-Bewertung der Textqualität selbst — ehrlich als "erste
Ansatzpunkte" kommuniziert, nicht als abschliessendes Urteil.

## Lokal testen

```bash
pip install flask requests beautifulsoup4
python3 checker_server.py
```

Läuft dann auf `http://localhost:8913`. Die Seiten rufen standardmässig
`http://localhost:8913/api/check?url=...` auf (siehe `AMATCH_CHECK_API` in
`script.js`, im Abschnitt "Stellenanzeigen-Check").

## Wichtig: das braucht echtes Hosting

Der Rest der Website ist statisches HTML/CSS/JS — läuft auf praktisch
jedem Webhosting. Dieser Ordner ist anders: ein **echter Python-Server**,
der eine laufende Umgebung braucht (nicht nur Dateien hochladen). Sobald
amatch.ch ein festes Hosting hat:

- **Kleiner Cloud-Server** (Render, Railway, Fly.io, PythonAnywhere): am
  einfachsten, da der Server hier schon fertig ist — `backend/` dorthin
  deployen.
- **Serverless-Funktion** (Vercel, Cloudflare Workers, Netlify Functions):
  braucht etwas Anpassung der Check-Logik an das Funktionsformat, aber gut
  machbar mit derselben Logik aus `checker_server.py`.

Danach in `script.js` die Zeile

```js
var CHECK_API = (window.AMATCH_CHECK_API || 'http://localhost:8913') + '/api/check';
```

auf die echte Backend-URL zeigen lassen — entweder den Fallback-Wert
anpassen, oder vor dem Laden von `script.js` in jeder HTML-Seite setzen:

```html
<script>window.AMATCH_CHECK_API = 'https://check-api.amatch.ch';</script>
<script src="script.js" defer></script>
```

Bis dahin funktioniert der Check nur lokal während der Weiterentwicklung.
