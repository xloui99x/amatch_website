"""A Match job-ad check: fetch a job ad, score its content, optionally e-mail the result."""

from .analysis import Report, analyze_html
from .app import create_app

__all__ = ["Report", "analyze_html", "create_app"]
