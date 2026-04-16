"""
govuk.py — Live GOV.UK Content API and Search API client.

Uses two public, unauthenticated APIs:
  Search:  https://www.gov.uk/api/search.json?q=<query>&count=<n>
  Content: https://www.gov.uk/api/content/<path>

No API key required. All requests use a short timeout to avoid blocking
the Streamlit UI.

Key public functions
--------------------
infer_organisations(query)  — map query keywords to relevant dept slugs
search_govuk(query, ...)    — call Search API with org + doc-type filters
fetch_govuk_page(path)      — fetch a single content item, incl. guide parts
page_to_document(page)      — convert GovUKPage → GovernmentDocument
augment_query(query, ...)   — high-level: search, fetch, return pages + docs
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from .schema import GovernmentDocument, Section

_SEARCH_URL = "https://www.gov.uk/api/search.json"
_CONTENT_URL = "https://www.gov.uk/api/content"
_TIMEOUT = 5  # seconds — keeps UI responsive

# ---------------------------------------------------------------------------
# Department / organisation inference
#
# Maps lower-case topic keywords to GOV.UK organisation slugs.
# These slugs are used as filter_organisations[] params in the Search API.
# ---------------------------------------------------------------------------

_TOPIC_TO_ORG: dict[str, list[str]] = {
    # Housing & benefits
    "housing benefit":          ["department-for-work-pensions"],
    "discretionary housing":    ["department-for-work-pensions"],
    "council tax":              ["department-for-levelling-up-housing-and-communities"],
    "council tax reduction":    ["department-for-levelling-up-housing-and-communities"],
    "homelessness":             ["department-for-levelling-up-housing-and-communities"],
    "right to buy":             ["department-for-levelling-up-housing-and-communities"],
    "social housing":           ["department-for-levelling-up-housing-and-communities"],
    "universal credit":         ["department-for-work-pensions"],
    "pip":                      ["department-for-work-pensions"],
    "personal independence":    ["department-for-work-pensions"],
    "disability benefit":       ["department-for-work-pensions"],
    "attendance allowance":     ["department-for-work-pensions"],
    "state pension":            ["department-for-work-pensions"],
    "pension credit":           ["department-for-work-pensions"],
    "jobseekers":               ["department-for-work-pensions"],
    "income support":           ["department-for-work-pensions"],
    "overpayment":              ["department-for-work-pensions"],
    "benefit":                  ["department-for-work-pensions"],
    # Employment & business
    "minimum wage":             ["department-for-business-and-trade", "hm-revenue-customs"],
    "national living wage":     ["department-for-business-and-trade"],
    "statutory sick pay":       ["hm-revenue-customs", "department-for-business-and-trade"],
    "sick pay":                 ["hm-revenue-customs"],
    "statutory maternity":      ["hm-revenue-customs"],
    "statutory paternity":      ["hm-revenue-customs"],
    "self-employed":            ["hm-revenue-customs"],
    "self employment":          ["hm-revenue-customs"],
    "workplace pension":        ["the-pensions-regulator", "department-for-work-pensions"],
    "auto enrolment":           ["the-pensions-regulator"],
    "employment rights":        ["department-for-business-and-trade"],
    "flexible working":         ["department-for-business-and-trade"],
    "redundancy":               ["department-for-business-and-trade"],
    "unfair dismissal":         ["department-for-business-and-trade"],
    "starting a business":      ["department-for-business-and-trade"],
    "small business":           ["department-for-business-and-trade"],
    "registering a company":    ["companies-house"],
    "companies house":          ["companies-house"],
    # Tax
    "income tax":               ["hm-revenue-customs"],
    "corporation tax":          ["hm-revenue-customs"],
    "vat":                      ["hm-revenue-customs"],
    "paye":                     ["hm-revenue-customs"],
    "capital gains":            ["hm-revenue-customs"],
    "tax":                      ["hm-revenue-customs"],
    # Procurement & spending
    "procurement":              ["cabinet-office"],
    "spending controls":        ["hm-treasury"],
    "public spending":          ["hm-treasury"],
    # Data & compliance
    "data protection":          ["information-commissioners-office"],
    "gdpr":                     ["information-commissioners-office"],
    "freedom of information":   ["cabinet-office"],
    "foi":                      ["cabinet-office"],
    # Immigration
    "immigration":              ["home-office"],
    "visa":                     ["home-office"],
    "right to work":            ["home-office"],
}

# Only retrieve these document types — excludes press releases, statistics,
# consultation outcomes, etc. which are rarely useful for a caseworker query.
_USEFUL_DOC_TYPES: set[str] = {
    "guide",
    "detailed_guide",
    "answer",
    "help_page",
    "transaction",
    "local_transaction",
    "simple_smart_answer",
    "smart_answer",
    "policy_paper",
    "document_collection",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class GovUKSearchResult:
    title: str
    description: str
    link: str                        # e.g. "/housing-benefit"
    document_type: str
    public_updated_at: Optional[str] = None
    organisations: list[str] = field(default_factory=list)


@dataclass
class GovUKPage:
    title: str
    description: str
    base_path: str
    document_type: str
    public_updated_at: Optional[str]
    organisations: list[str]
    excerpt: str                     # first ~600 chars of plain body text
    full_body: str                   # complete plain text (for conversion)
    sections: list[dict]             # [{"heading": str, "body": str}, ...]
    govuk_url: str                   # canonical https://www.gov.uk<base_path>


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _extract_orgs(content_json: dict) -> list[str]:
    """Return a list of organisation titles from a content API response."""
    links = content_json.get("links") or {}
    orgs = links.get("organisations") or []
    return [o.get("title", "") for o in orgs if isinstance(o, dict)]


def _extract_topics(content_json: dict) -> list[str]:
    """Return topic titles from taxons or topic links."""
    links = content_json.get("links") or {}
    taxons = links.get("taxons") or []
    return [t.get("title", "") for t in taxons if isinstance(t, dict) and t.get("title")]


def _body_from_details(details: dict) -> str:
    """Extract plain text body from the details block of a content item."""
    body = (
        details.get("body")
        or details.get("introduction")
        or details.get("summary")
        or ""
    )
    if isinstance(body, list):
        body = " ".join(
            part.get("body", "") if isinstance(part, dict) else str(part)
            for part in body
        )
    return _strip_html(str(body))


def _extract_sections_and_body(content_json: dict) -> tuple[list[dict], str]:
    """
    Return (sections, full_body) from a GOV.UK content item.

    For guide-type documents the Content API returns each part as an entry
    in details.parts — we treat each part as a separate section so the
    TF-IDF index gets finer-grained retrieval.

    For all other types we fall back to a single section containing
    the full body text.
    """
    details = content_json.get("details") or {}
    parts = details.get("parts") or []

    if parts:
        sections: list[dict] = []
        body_parts: list[str] = []
        for part in parts:
            heading = part.get("title", "")
            raw = part.get("body", "")
            body = _strip_html(str(raw)) if raw else ""
            if heading or body:
                sections.append({"heading": heading, "body": body})
                body_parts.append(f"{heading} {body}".strip())
        full_body = " ".join(body_parts)
        return sections, full_body

    # Single-body types
    body = _body_from_details(details)
    if not body:
        body = _strip_html(str(content_json.get("body") or ""))
    sections = [{"heading": content_json.get("title", ""), "body": body}] if body else []
    return sections, body


# ---------------------------------------------------------------------------
# Department inference
# ---------------------------------------------------------------------------

def infer_organisations(query: str) -> list[str]:
    """
    Return a list of GOV.UK organisation slugs that are likely to hold
    content relevant to *query*, based on keyword matching.

    The returned slugs can be passed directly to search_govuk() as the
    *organisations* parameter to narrow Search API results.
    """
    q_lower = query.lower()
    slugs: list[str] = []
    seen: set[str] = set()
    for keyword, org_slugs in _TOPIC_TO_ORG.items():
        if keyword in q_lower:
            for slug in org_slugs:
                if slug not in seen:
                    slugs.append(slug)
                    seen.add(slug)
    return slugs


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------

def search_govuk(
    query: str,
    count: int = 5,
    organisations: Optional[list[str]] = None,
    doc_types: Optional[list[str]] = None,
) -> list[GovUKSearchResult]:
    """
    Query the GOV.UK Search API.

    Parameters
    ----------
    query         : free-text search terms
    count         : max results to request
    organisations : list of org slugs to filter on (OR logic within the list)
    doc_types     : list of document_type values to restrict to; defaults to
                    _USEFUL_DOC_TYPES if None
    """
    if doc_types is None:
        doc_types = list(_USEFUL_DOC_TYPES)

    # Build params as a list of tuples to support repeated keys
    params: list[tuple[str, str]] = [("q", query), ("count", str(count))]
    for org in (organisations or []):
        params.append(("filter_organisations[]", org))
    for dt in doc_types:
        params.append(("filter_document_type[]", dt))

    try:
        resp = requests.get(
            _SEARCH_URL,
            params=params,
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results: list[GovUKSearchResult] = []
    for item in data.get("results", []):
        results.append(
            GovUKSearchResult(
                title=item.get("title", ""),
                description=_strip_html(item.get("description", "")),
                link=item.get("link", ""),
                document_type=item.get("document_type", ""),
                public_updated_at=item.get("public_timestamp"),
                organisations=[
                    o.get("title", "")
                    for o in item.get("organisations", [])
                    if isinstance(o, dict)
                ],
            )
        )
    return results


# ---------------------------------------------------------------------------
# Content API
# ---------------------------------------------------------------------------

def fetch_govuk_page(path: str) -> Optional[GovUKPage]:
    """
    Fetch a single GOV.UK content item by its path (e.g. "/housing-benefit").

    Multi-part guides have their parts extracted as separate sections so that
    finer-grained passage retrieval is possible.  Returns None on any error.
    """
    if not path.startswith("/"):
        path = "/" + path

    try:
        resp = requests.get(
            f"{_CONTENT_URL}{path}",
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    sections, full_body = _extract_sections_and_body(data)
    excerpt = full_body[:600] + ("…" if len(full_body) > 600 else "")

    return GovUKPage(
        title=data.get("title", path),
        description=_strip_html(data.get("description", "")),
        base_path=data.get("base_path", path),
        document_type=data.get("document_type", ""),
        public_updated_at=data.get("public_updated_at"),
        organisations=_extract_orgs(data),
        excerpt=excerpt,
        full_body=full_body,
        sections=sections,
        govuk_url=f"https://www.gov.uk{data.get('base_path', path)}",
    )


# ---------------------------------------------------------------------------
# GovernmentDocument converter
# ---------------------------------------------------------------------------

def page_to_document(page: GovUKPage) -> GovernmentDocument:
    """
    Convert a GovUKPage into a GovernmentDocument so it can be added to
    a DocumentIndex and ranked alongside local corpus results.

    document_id is derived from the base_path so it is stable across calls.
    source_format is set to "govuk-api" to distinguish live content.
    """
    # Stable ID from base_path: /housing-benefit → GOVUK-housing-benefit
    doc_id = "GOVUK-" + page.base_path.lstrip("/").replace("/", "-")

    pub_date = (page.public_updated_at or "")[:10] or None  # "YYYY-MM-DD"

    schema_sections = [
        Section(heading=s["heading"], level=2, body=s["body"])
        for s in page.sections
        if s.get("body")
    ]
    if not schema_sections and page.full_body:
        schema_sections = [Section(heading=page.title, level=1, body=page.full_body)]

    return GovernmentDocument(
        document_id=doc_id,
        title=page.title,
        department=", ".join(page.organisations) or None,
        document_type=page.document_type,
        status="current",           # live GOV.UK content is always current
        publication_date=pub_date,
        last_updated=pub_date,
        audience=None,
        topics=[],                  # populated from taxons if needed
        version=None,
        supersedes=None,
        related_documents=[],
        sections=schema_sections,
        tables=[],
        keywords=[],
        quality_flags=[],
        raw_text=page.full_body,
        source_file=page.govuk_url,
        source_format="govuk-api",
    )


# ---------------------------------------------------------------------------
# High-level convenience function
# ---------------------------------------------------------------------------

def augment_query(
    query: str,
    max_results: int = 3,
) -> tuple[list[GovUKPage], list[GovernmentDocument], list[str]]:
    """
    Search GOV.UK for *query* using inferred department filters, fetch full
    page content for the top hits, and convert each to a GovernmentDocument.

    Returns
    -------
    pages     : GovUKPage list — for direct rendering in the UI
    documents : GovernmentDocument list — ready to add to a DocumentIndex
    inferred_orgs : list of org slugs that were used to filter the search
    """
    inferred_orgs = infer_organisations(query)

    # First pass: search with org filter (more relevant results)
    search_hits = search_govuk(query, count=max_results + 3, organisations=inferred_orgs)

    # Fallback: if no org-filtered results, broaden to all useful doc types
    if not search_hits:
        search_hits = search_govuk(query, count=max_results + 3, organisations=None)

    pages: list[GovUKPage] = []
    documents: list[GovernmentDocument] = []
    for hit in search_hits:
        if len(pages) >= max_results:
            break
        page = fetch_govuk_page(hit.link)
        if page and page.full_body:
            pages.append(page)
            documents.append(page_to_document(page))

    return pages, documents, inferred_orgs
