"""E-mail report: a branded score chart plus the weakest findings, sent via Resend."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from html import escape

import requests
from PIL import Image, ImageDraw, ImageFont

from .analysis import Report
from .i18n import BOOKING_URLS, EMAIL_TEXTS, Lang

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Brand colours (RGB)
NAVY = (27, 53, 87)
ORANGE = (232, 98, 44)
TRACK = (236, 225, 211)
MUTED = (75, 85, 99)
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class ResendConfig:
    api_key: str
    sender: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def render_score_chart(report: Report, lang: Lang) -> bytes:
    """PNG bar chart: overall score followed by the four category scores."""
    rows = [(EMAIL_TEXTS[lang]["overall"], report.overall)]
    rows += [(name, category.score) for name, category in report.categories.items()]

    font = _font(22)
    row_height, width = 68, 720
    image = Image.new("RGB", (width, 40 + len(rows) * row_height), WHITE)
    draw = ImageDraw.Draw(image)

    bar_x, bar_width, bar_height, radius = 250, 360, 26, 13
    y = 24
    for label, raw_score in rows:
        score = max(0, min(100, raw_score))
        draw.text((0, y + 3), label, fill=NAVY, font=font)
        draw.rounded_rectangle(
            [bar_x, y, bar_x + bar_width, y + bar_height], radius=radius, fill=TRACK
        )
        fill_width = round(bar_width * score / 100)
        if fill_width >= bar_height:
            draw.rounded_rectangle(
                [bar_x, y, bar_x + fill_width, y + bar_height], radius=radius, fill=ORANGE
            )
        elif fill_width > 0:
            # Too short for a rounded bar: draw a dot so low scores stay visible.
            draw.ellipse([bar_x, y, bar_x + bar_height, y + bar_height], fill=ORANGE)
        draw.text((bar_x + bar_width + 18, y + 3), f"{score}/100", fill=MUTED, font=font)
        y += row_height

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_email_html(report: Report, lang: Lang) -> str:
    """Inline-styled HTML (mail clients ignore <style>). All dynamic text is escaped."""
    texts = EMAIL_TEXTS[lang]
    weak = report.weakest_checks()
    if weak:
        items = "".join(
            f'<li style="margin-bottom:8px;"><strong>{escape(check.name)}:</strong> '
            f"{escape(check.finding)}</li>"
            for check in weak
        )
    else:
        items = f"<li>{escape(texts['all_good'])}</li>"

    alt = f"{texts['overall']}: {report.overall}/100"
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;padding:8px;">
      <h2 style="color:#1B3557;font-size:19px;margin:0 0 8px;">{escape(texts["intro"])}</h2>
      <p style="color:#4B5563;font-size:14px;word-break:break-all;margin:0 0 20px;">{escape(report.url)}</p>
      <img src="cid:scorechart" alt="{escape(alt)}" width="600" style="width:100%;max-width:600px;height:auto;display:block;border:1px solid #ECE1D3;border-radius:12px;" />
      <h3 style="color:#1B3557;font-size:16px;margin:28px 0 10px;">{escape(texts["findings_title"])}</h3>
      <ul style="color:#4B5563;font-size:14px;line-height:1.6;padding-left:20px;margin:0;">{items}</ul>
      <p style="margin:28px 0 0;">
        <a href="{escape(BOOKING_URLS[lang])}" style="background:#E8622C;color:#171E29;padding:13px 26px;border-radius:999px;text-decoration:none;font-weight:bold;font-size:15px;display:inline-block;">{escape(texts["cta_btn"])}</a>
      </p>
    </div>
    """  # noqa: E501 - inline e-mail styles are clearer on one line


def send_report_email(
    to_email: str,
    report: Report,
    lang: Lang,
    config: ResendConfig,
    *,
    session: requests.Session | None = None,
) -> bool:
    """Sends the report. Returns False if Resend rejects the request."""
    chart = base64.b64encode(render_score_chart(report, lang)).decode("ascii")
    payload = {
        "from": config.sender,
        "to": [to_email],
        "subject": EMAIL_TEXTS[lang]["subject"],
        "html": build_email_html(report, lang),
        "attachments": [{"filename": "score.png", "content": chart, "content_id": "scorechart"}],
    }
    response = (session or requests).post(
        RESEND_ENDPOINT,
        json=payload,
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=15,
    )
    return bool(response.ok)


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no size argument
        return ImageFont.load_default()
