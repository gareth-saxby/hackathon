"""
extractor.py — Parse HTML, Markdown, and TXT government documents into GovernmentDocument objects.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import frontmatter
from bs4 import BeautifulSoup, Tag

from .schema import GovernmentDocument, QualityFlag, Section, Table

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = ("title", "department", "publication_date")
_STALE_MONTHS = 12


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Try to parse a date string in several ISO-like formats."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _flag_stale(doc: GovernmentDocument) -> bool:
    """FR-10: status=current but last_updated > 12 months ago."""
    if doc.status and doc.status.lower() == "current":
        lu = _parse_date(doc.last_updated) or _parse_date(doc.publication_date)
        if lu:
            months_old = (date.today() - lu).days / 30.44
            if months_old > _STALE_MONTHS:
                return True
    return False


def _flag_missing_metadata(doc: GovernmentDocument) -> bool:
    """FR-12: missing title, department, or publication_date."""
    return any(
        not getattr(doc, f, None)
        for f in _REQUIRED_FIELDS
    )


# ---------------------------------------------------------------------------
# HTML parser (FR-01)
# ---------------------------------------------------------------------------

def _parse_meta(soup: BeautifulSoup, name: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _extract_tables_from_soup(soup: BeautifulSoup) -> List[Table]:
    tables: List[Table] = []
    for tbl in soup.find_all("table"):
        caption_tag = tbl.find("caption")
        caption = caption_tag.get_text(strip=True) if caption_tag else None

        headers: List[str] = []
        thead = tbl.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]
        else:
            first_row = tbl.find("tr")
            if first_row:
                ths = first_row.find_all("th")
                if ths:
                    headers = [th.get_text(strip=True) for th in ths]

        rows: List[List[str]] = []
        for tr in tbl.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells and cells != headers:
                rows.append(cells)

        if headers or rows:
            tables.append(Table(caption=caption, headers=headers, rows=rows))
    return tables


def parse_html(path: Path) -> GovernmentDocument:
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    # --- metadata from <meta> tags ---
    doc_id = _parse_meta(soup, "document-id") or path.stem
    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) if title_tag else None) or doc_id

    # Strip site suffix if present (e.g. " - GOV.UK")
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()

    department = _parse_meta(soup, "department") or _parse_meta(soup, "author")
    status = _parse_meta(soup, "status")
    pub_date = _parse_meta(soup, "publication-date")
    last_updated = _parse_meta(soup, "last-updated")
    audience = _parse_meta(soup, "audience")
    doc_type = _parse_meta(soup, "document-type")
    topics_raw = _parse_meta(soup, "topics")
    topics = [t.strip() for t in topics_raw.split(",")] if topics_raw else []
    version = _parse_meta(soup, "version")
    supersedes = _parse_meta(soup, "supersedes")

    related_raw = _parse_meta(soup, "related-documents")
    related_documents = (
        [r.strip() for r in related_raw.split(",")] if related_raw else []
    )

    # --- sections from headings ---
    sections: List[Section] = []
    body_tag = soup.find("body") or soup
    heading_tags = body_tag.find_all(re.compile(r"^h[1-6]$"))

    for i, htag in enumerate(heading_tags):
        level = int(htag.name[1])
        heading_text = htag.get_text(strip=True)
        # Collect sibling text until the next heading
        body_parts: List[str] = []
        for sibling in htag.next_siblings:
            if isinstance(sibling, Tag) and re.match(r"^h[1-6]$", sibling.name):
                break
            if isinstance(sibling, Tag):
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    body_parts.append(text)
        sections.append(
            Section(heading=heading_text, level=level, body=" ".join(body_parts))
        )

    # Fall back: if no sections found, use all body text
    if not sections:
        body_text = body_tag.get_text(separator=" ", strip=True)
        sections.append(Section(heading="Document", level=1, body=body_text))

    tables = _extract_tables_from_soup(soup)

    doc = GovernmentDocument(
        document_id=doc_id,
        title=title,
        department=department,
        document_type=doc_type,
        status=status,
        publication_date=pub_date,
        last_updated=last_updated,
        audience=audience,
        topics=topics,
        version=version,
        supersedes=supersedes,
        related_documents=related_documents,
        sections=sections,
        tables=tables,
        source_file=str(path),
        source_format="html",
    )

    _apply_per_doc_flags(doc)
    return doc


# ---------------------------------------------------------------------------
# Markdown parser (FR-02)
# ---------------------------------------------------------------------------

def _md_sections(body: str) -> List[Section]:
    """Split markdown body into sections by ATX headings."""
    lines = body.splitlines()
    sections: List[Section] = []
    current_heading = "Document"
    current_level = 1
    current_body: List[str] = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if current_body:
                sections.append(
                    Section(
                        heading=current_heading,
                        level=current_level,
                        body="\n".join(current_body).strip(),
                    )
                )
            current_heading = m.group(2).strip()
            current_level = len(m.group(1))
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        sections.append(
            Section(
                heading=current_heading,
                level=current_level,
                body="\n".join(current_body).strip(),
            )
        )

    return [s for s in sections if s.body.strip()]


def parse_markdown(path: Path) -> GovernmentDocument:
    post = frontmatter.load(str(path))
    meta = post.metadata
    body = post.content

    doc_id = str(meta.get("document_id", "")).strip() or path.stem
    title = str(meta.get("title", "")).strip() or doc_id
    department = str(meta.get("department", "")).strip() or None
    doc_type = str(meta.get("type", meta.get("document_type", ""))).strip() or None
    status = str(meta.get("status", "")).strip() or None
    pub_date = str(meta.get("publication_date", "")).strip() or None
    last_updated = str(meta.get("last_updated", "")).strip() or None
    audience = str(meta.get("audience", "")).strip() or None
    version = str(meta.get("version", "")).strip() or None
    supersedes_raw = meta.get("supersedes")
    supersedes = str(supersedes_raw).strip() if supersedes_raw else None

    topics_raw = meta.get("topics", [])
    if isinstance(topics_raw, list):
        topics = [str(t).strip() for t in topics_raw]
    else:
        topics = [t.strip() for t in str(topics_raw).split(",")]

    related_raw = meta.get("related_documents", [])
    if isinstance(related_raw, list):
        related_documents = [str(r).strip() for r in related_raw]
    else:
        related_documents = [r.strip() for r in str(related_raw).split(",")]

    sections = _md_sections(body)
    if not sections:
        sections = [Section(heading="Document", level=1, body=body.strip())]

    doc = GovernmentDocument(
        document_id=doc_id,
        title=title,
        department=department,
        document_type=doc_type,
        status=status,
        publication_date=pub_date,
        last_updated=last_updated,
        audience=audience,
        topics=topics,
        version=version,
        supersedes=supersedes,
        related_documents=related_documents,
        sections=sections,
        source_file=str(path),
        source_format="markdown",
    )

    _apply_per_doc_flags(doc)
    return doc


# ---------------------------------------------------------------------------
# Plain-text parser (FR-03)
# ---------------------------------------------------------------------------

_TXT_META_PATTERNS = {
    "document_id": re.compile(r"^Document\s+ID[:\s]+(.+)$", re.I),
    "title": re.compile(r"^Title[:\s]+(.+)$", re.I),
    "department": re.compile(r"^Department[:\s]+(.+)$", re.I),
    "status": re.compile(r"^Status[:\s]+(.+)$", re.I),
    "publication_date": re.compile(r"^Published[:\s]+(.+)$", re.I),
    "last_updated": re.compile(r"^Last[\s_]updated[:\s]+(.+)$", re.I),
    "audience": re.compile(r"^Audience[:\s]+(.+)$", re.I),
    "version": re.compile(r"^Version[:\s]+(.+)$", re.I),
}

# Heading heuristics: numbered "1. Title" or ALL-CAPS lines >= 4 chars
_TXT_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s{1,4}([A-Z].{2,})")
_TXT_ALLCAPS = re.compile(r"^[A-Z][A-Z\s\-:,/&]{10,}$")


def _parse_txt_meta(lines: List[str]) -> dict:
    meta: dict = {}
    for line in lines[:30]:  # metadata typically in first 30 lines
        stripped = line.strip()
        for key, pattern in _TXT_META_PATTERNS.items():
            if key not in meta:
                m = pattern.match(stripped)
                if m:
                    meta[key] = m.group(1).strip()
    return meta


def _txt_sections(lines: List[str]) -> List[Section]:
    sections: List[Section] = []
    current_heading = "Document"
    current_level = 1
    current_body: List[str] = []

    for line in lines:
        stripped = line.strip()
        m_num = _TXT_HEADING.match(stripped)
        m_caps = _TXT_ALLCAPS.match(stripped)

        if m_num:
            if current_body:
                sections.append(
                    Section(
                        heading=current_heading,
                        level=current_level,
                        body="\n".join(current_body).strip(),
                    )
                )
            numbering = m_num.group(1)
            current_level = numbering.count(".") + 1
            current_heading = m_num.group(2).strip()
            current_body = []
        elif m_caps and len(stripped) > 4:
            if current_body:
                sections.append(
                    Section(
                        heading=current_heading,
                        level=current_level,
                        body="\n".join(current_body).strip(),
                    )
                )
            current_heading = stripped.title()
            current_level = 1
            current_body = []
        else:
            if stripped:
                current_body.append(stripped)

    if current_body:
        sections.append(
            Section(
                heading=current_heading,
                level=current_level,
                body="\n".join(current_body).strip(),
            )
        )

    return [s for s in sections if s.body.strip()]


def parse_txt(path: Path) -> GovernmentDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # First non-empty line is often the document title if in ALL CAPS
    first_content = next((l.strip() for l in lines if l.strip()), "")
    inferred_title = first_content.title() if _TXT_ALLCAPS.match(first_content) else None

    meta = _parse_txt_meta(lines)

    doc_id = meta.get("document_id", path.stem)
    title = meta.get("title") or inferred_title or doc_id
    department = meta.get("department")
    status = meta.get("status")
    pub_date = meta.get("publication_date")
    last_updated = meta.get("last_updated")
    audience = meta.get("audience")
    version = meta.get("version")

    sections = _txt_sections(lines)
    if not sections:
        sections = [Section(heading="Document", level=1, body=text.strip())]

    doc = GovernmentDocument(
        document_id=doc_id,
        title=title,
        department=department,
        status=status,
        publication_date=pub_date,
        last_updated=last_updated,
        audience=audience,
        version=version,
        sections=sections,
        source_file=str(path),
        source_format="txt",
    )

    _apply_per_doc_flags(doc)
    return doc


# ---------------------------------------------------------------------------
# Per-document quality flags (FR-10, FR-12)
# ---------------------------------------------------------------------------

def _apply_per_doc_flags(doc: GovernmentDocument) -> None:
    if _flag_stale(doc):
        if QualityFlag.STALE not in doc.quality_flags:
            doc.quality_flags.append(QualityFlag.STALE)
    if _flag_missing_metadata(doc):
        if QualityFlag.MISSING_METADATA not in doc.quality_flags:
            doc.quality_flags.append(QualityFlag.MISSING_METADATA)


# ---------------------------------------------------------------------------
# Corpus-level quality flags (FR-11, FR-13)
# ---------------------------------------------------------------------------

def apply_corpus_flags(documents: List[GovernmentDocument]) -> None:
    """
    FR-11: Mark documents that are superseded by another doc in the corpus.
    FR-13: Flag cross-document contradictions for known numeric policy values.
    """
    # Build lookup: doc_id -> doc
    id_map = {doc.document_id: doc for doc in documents if doc.document_id}

    # FR-11: supersession
    for doc in documents:
        if doc.supersedes:
            # The doc that is superseded may be referenced by ID prefix
            for other in documents:
                if (
                    other.document_id != doc.document_id
                    and other.document_id in doc.supersedes
                ):
                    if QualityFlag.SUPERSEDED not in other.quality_flags:
                        other.quality_flags.append(QualityFlag.SUPERSEDED)

    # FR-13: contradictions — look for named numeric values in section bodies
    # Extract (doc_id, value_name, numeric_value) triples
    _check_contradictions(documents)


_POLICY_VALUE_PATTERNS = [
    # e.g. "capital limit of £16,000" or "capital threshold: £16,000"
    re.compile(
        r"(capital\s+(?:limit|threshold|disregard))[^\d£]*([£$]?[\d,]+(?:\.\d+)?)",
        re.I,
    ),
    # national minimum wage
    re.compile(
        r"(national\s+minimum\s+wage|nmw|national\s+living\s+wage)[^\d£]*([£$]?[\d.]+)",
        re.I,
    ),
    # SSP weekly rate
    re.compile(
        r"(statutory\s+sick\s+pay|ssp)[^\d£]*([£$]?[\d.]+)\s*(?:per\s+week|a\s+week|weekly)",
        re.I,
    ),
]


def _check_contradictions(documents: List[GovernmentDocument]) -> None:
    """Simple heuristic: find the same named policy value with differing amounts."""
    value_map: dict[str, dict[str, str]] = {}  # policy_key -> {doc_id: value}

    for doc in documents:
        full_text = " ".join(s.body for s in doc.sections)
        for pattern in _POLICY_VALUE_PATTERNS:
            for m in pattern.finditer(full_text):
                key = re.sub(r"\s+", "_", m.group(1).lower().strip())
                val = m.group(2).strip()
                if key not in value_map:
                    value_map[key] = {}
                value_map[key][doc.document_id] = val

    id_map = {doc.document_id: doc for doc in documents}
    for key, doc_vals in value_map.items():
        distinct = set(doc_vals.values())
        if len(distinct) > 1:
            for doc_id in doc_vals:
                doc = id_map.get(doc_id)
                if doc and QualityFlag.CONTRADICTION not in doc.quality_flags:
                    doc.quality_flags.append(QualityFlag.CONTRADICTION)


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------

def extract_all(data_dir: Path) -> List[GovernmentDocument]:
    """Parse every supported file in *data_dir* and return GovernmentDocuments."""
    parsers = {
        ".html": parse_html,
        ".htm": parse_html,
        ".md": parse_markdown,
        ".txt": parse_txt,
    }

    documents: List[GovernmentDocument] = []
    for path in sorted(data_dir.iterdir()):
        parser = parsers.get(path.suffix.lower())
        if parser:
            try:
                doc = parser(path)
                documents.append(doc)
            except Exception as exc:
                print(f"[extractor] WARNING: failed to parse {path.name}: {exc}")

    apply_corpus_flags(documents)
    return documents


def save_extracted(documents: List[GovernmentDocument], output_dir: Path) -> None:
    """Save each document as a JSON file in *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for doc in documents:
        out_path = output_dir / f"{doc.document_id}.json"
        out_path.write_text(
            json.dumps(doc.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def load_extracted(output_dir: Path) -> List[GovernmentDocument]:
    """Load previously extracted documents from JSON files."""
    from .schema import GovernmentDocument as GD

    docs: List[GovernmentDocument] = []
    for path in sorted(output_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        docs.append(GD.from_dict(data))
    return docs
