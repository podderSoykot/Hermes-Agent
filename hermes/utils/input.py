"""Normalize user input for BD pipeline."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from hermes.models.bd import BDPipelineRequest


def extract_domain(value: str | None) -> str | None:
    """Turn a URL or domain string into a clean hostname (e.g. pst.ag)."""
    if not value or not value.strip():
        return None
    raw = value.strip().rstrip("/")
    if "://" in raw or raw.startswith("www."):
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = parsed.netloc or parsed.path.split("/")[0]
    else:
        host = raw.split("/")[0]
    host = host.removeprefix("www.")
    return host.lower() if host else None


def domain_to_company_name(domain: str) -> str:
    """Derive a display company name from a domain (pst.ag -> PST AG)."""
    slug = domain.split(".")[0]
    if slug.isalpha() and len(slug) <= 5:
        return slug.upper()
    return slug.replace("-", " ").replace("_", " ").title()


def _looks_like_url(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith("http://") or v.startswith("https://") or v.startswith("www.") or (
        "." in v and " " not in v and "/" in v
    )


def normalize_pipeline_request(request: BDPipelineRequest) -> BDPipelineRequest:
    """Clean URLs in company name / domain fields before agents run."""
    domain = extract_domain(request.domain) or extract_domain(request.company_name)
    name = request.company_name.strip()

    if _looks_like_url(name):
        if domain is None:
            domain = extract_domain(name)
        name = domain_to_company_name(domain) if domain else name

    if domain and not request.domain:
        pass  # use extracted domain

    return BDPipelineRequest(
        company_name=name,
        domain=domain,
        industry=(request.industry or "").strip() or None,
        target_contact_title=request.target_contact_title,
        product_offering=request.product_offering,
        sender_name=request.sender_name,
        sender_company=request.sender_company,
        schedule_follow_up=request.schedule_follow_up,
    )
