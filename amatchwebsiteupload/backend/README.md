# Job-ad check backend

The service behind the **Stellenanzeigen-Check** on
[amatch.ch](https://amatch.ch/stellencheck.html). A business owner pastes the
link to a job ad; the server downloads the page, scores its *content* (not
SEO) in four categories and can e-mail the result with a chart.

## How it works

```
browser ──GET /api/check?url=…──▶ app.py ──▶ safe_fetch.py ──▶ job ad (public web)
                                     │
                                     └──▶ analysis.py ──▶ JSON report ──▶ script.js renders it
browser ──POST /api/send-report──▶ app.py ──▶ report_email.py ──▶ Resend API ──▶ inbox
```

| Module | Responsibility |
|---|---|
| `amatch_checker/analysis.py` | 16 rule-based checks in 4 categories, scoring. Pure function of the HTML. |
| `amatch_checker/safe_fetch.py` | Downloads user-supplied URLs without SSRF (see below). |
| `amatch_checker/report_email.py` | PNG score chart (Pillow) and the HTML e-mail. |
| `amatch_checker/app.py` | Flask routes, validation, CORS, rate limits. |
| `amatch_checker/i18n.py` | All texts in German, French and English. |
| `checker_server.py` | Entry point (`gunicorn checker_server:app`). |

### What is checked

| Category | Checks |
|---|---|
| Role description | text length (150–700 words), concrete details (workload, EFZ…), list structure, meaningful title |
| Application process | visible e-mail/phone (links *and* plain text, Swiss number formats), WhatsApp, form length, call to action |
| Employer benefits | salary, training, team/culture, extras |
| Reach | mobile viewport, direct address of the reader, images, social preview (Open Graph) |

A category score is the share of passed checks. The checks are keyword and
structure detection, so the page presents them honestly as *first pointers*.

## Security

The endpoint fetches arbitrary URLs typed in by visitors, which makes it a
classic target for **server-side request forgery**. `safe_fetch.py`:

- allows only `http`/`https` on ports 80/443 and rejects credentials in URLs
- resolves the host and rejects it if *any* address is private, loopback,
  link-local (e.g. the `169.254.169.254` cloud metadata service) or reserved
- follows redirects manually and validates **every hop**, so a public page
  cannot bounce the server to an internal address
- caps the response at 3 MB and times out after 8 s

On top of that, `app.py` rate-limits checks (20/min) and e-mails (5/h) per
client and only sends CORS headers to configured origins. All values that end
up in the e-mail are HTML-escaped.

## Run locally

```bash
cd amatchwebsiteupload/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python3 checker_server.py            # http://localhost:8913
```

Serve the website from `amatchwebsiteupload/` (for example
`python3 -m http.server 8000`) and open
`http://localhost:8000/stellencheck.html`; on localhost `script.js` calls the
local backend automatically.

## Quality checks

```bash
pytest          # 94 tests: every check, scoring, SSRF cases, HTTP API, e-mail
ruff check .    # lint
mypy amatch_checker checker_server.py   # strict type checking
```

They also run on every push via GitHub Actions.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RESEND_API_KEY` | – | Enables `/api/send-report`. Without it the endpoint answers 503. |
| `RESEND_FROM` | `A Match <onboarding@resend.dev>` | Sender address. |
| `AMATCH_ALLOWED_ORIGINS` | `https://amatch.ch,https://www.amatch.ch,http://localhost:8000,http://127.0.0.1:8000` | Comma-separated origins allowed to call the API from a browser. `*` allows all. |
| `PORT` | `8913` | Port for `python3 checker_server.py`. |

## Deployment (Render)

- Root directory: `amatchwebsiteupload/backend`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn checker_server:app`
- Set `RESEND_API_KEY` and, if the site is served from a domain other than
  amatch.ch, `AMATCH_ALLOWED_ORIGINS`.

The frontend points at the deployed URL in `script.js` (`DEFAULT_CHECK_API`),
or per page via `window.AMATCH_CHECK_API`.
