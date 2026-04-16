"""
Document extractor for government guidance files.
Supports: HTML, Markdown, plain text.
Challenge 2: Unlocking the Dark Data — DSIT AI Engineering Lab Hackathon 2026
"""

import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from .schema import GovernmentDocument, Section, TableData


# ---------------------------------------------------------------------------
# Shared helper: extract keywords from raw text
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "be",
    "for", "on", "with", "that", "this", "it", "at", "by", "from", "as",
    "has", "have", "may", "must", "will", "not", "any", "if", "their",
    "which", "who", "been", "they", "you", "your", "its", "was", "were",
}


def _extract_keywords(text: str, top_n: int = 20) -> List[str]:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    freq: dict = {}
    for w in words:
        if w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


# ---------------------------------------------------------------------------
# HTML extractor
# ---------------------------------------------------------------------------

def _extract_html(content: str, source_file: str) -> GovernmentDocument:
    soup = BeautifulSoup(content, "html.parser")

    def meta(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"].strip() if tag and tag.get("content") else None

    document_id = meta("document-id") or Path(source_file).stem.upper()
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else Path(source_file).stem
    department = meta("author") or meta("department")
    doc_type = meta("document-type")
    status = meta("status")
    pub_date = meta("publication-date")
    last_updated = meta("last-updated")
    audience = meta("audience")
    topics = [t.strip() for t in (meta("topics") or "").split(",") if t.strip()]

    sections: List[Section] = []
    for tag in soup.find_all(["h2", "h3", "h4"]):
        level = int(tag.name[1])
        heading = tag.get_text(strip=True)
        body_parts = []
        for sibling in tag.find_next_siblings():
            if sibling.name in ["h2", "h3", "h4"]:
                break
            # Include block-level tags only; skip <li> to avoid duplication via parent <ul>/<ol>
            if sibling.name in ["p", "ul", "ol", "div"]:
                body_parts.append(sibling.get_text(" ", strip=True))
        sections.append(Section(heading=heading, level=level, body=" ".join(body_parts)))

    tables: List[TableData] = []
    for tbl in soup.find_all("table"):
        caption_tag = tbl.find("caption")
        caption = caption_tag.get_text(strip=True) if caption_tag else None
        headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
        rows = [
            [td.get_text(strip=True) for td in tr.find_all("td")]
            for tr in tbl.find_all("tr")
            if tr.find_all("td")
        ]
        if headers or rows:
            tables.append(TableData(caption=caption, headers=headers, rows=rows))

    raw_text = soup.get_text(" ", strip=True)

    return GovernmentDocument(
        document_id=document_id, title=title, department=department,
        document_type=doc_type, status=status, publication_date=pub_date,
        last_updated=last_updated, audience=audience, topics=topics,
        version=None, supersedes=None, related_documents=[],
        sections=sections, tables=tables,
        keywords=_extract_keywords(raw_text),
        quality_flags=[], raw_text=raw_text,
        source_file=source_file, source_format="html",
    )


# ---------------------------------------------------------------------------
# Markdown extractor
# ---------------------------------------------------------------------------

def _extract_markdown(content: str, source_file: str) -> GovernmentDocument:
    import frontmatter  # python-frontmatter
    import datetime as _dt

    def _to_str(val) -> Optional[str]:
        """Normalise date/datetime objects from YAML to ISO string."""
        if val is None:
            return None
        if isinstance(val, (_dt.date, _dt.datetime)):
            return val.isoformat()[:10]
        return str(val)

    post = frontmatter.loads(content)
    meta = post.metadata
    body_text = post.content

    document_id = meta.get("document_id", Path(source_file).stem.upper())
    title = meta.get("title", Path(source_file).stem)
    department = meta.get("department")
    doc_type = meta.get("type")
    status = meta.get("status")
    pub_date = _to_str(meta.get("publication_date") or meta.get("publication-date"))
    last_updated = _to_str(meta.get("last_updated") or meta.get("last-updated"))
    audience = meta.get("audience")
    topics_raw = meta.get("topics", [])
    raw_list = topics_raw if isinstance(topics_raw, list) else [topics_raw]
    # Flatten in case YAML produced nested lists; convert all to strings
    topics = [str(t).strip() for t in raw_list if t and not isinstance(t, list)] + \
             [str(item).strip() for t in raw_list if isinstance(t, list) for item in t]
    topics = [t for t in topics if t]
    version = str(meta.get("version")) if meta.get("version") else None
    supersedes = meta.get("supersedes")
    related_raw = meta.get("related_documents", [])
    related_documents = related_raw if isinstance(related_raw, list) else [related_raw]

    # Parse sections from Markdown headings
    sections: List[Section] = []
    current_heading = ""
    current_level = 2
    current_body: List[str] = []

    for line in body_text.splitlines():
        heading_match = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading_match:
            if current_heading:
                sections.append(Section(
                    heading=current_heading,
                    level=current_level,
                    body=" ".join(current_body).strip(),
                ))
            current_heading = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_body = []
        else:
            stripped = line.strip()
            if stripped:
                current_body.append(stripped)

    if current_heading:
        sections.append(Section(
            heading=current_heading,
            level=current_level,
            body=" ".join(current_body).strip(),
        ))

    # Parse Markdown tables (pipe-delimited)
    tables: List[TableData] = []
    table_lines: List[str] = []
    for line in body_text.splitlines():
        if "|" in line:
            table_lines.append(line)
        else:
            if len(table_lines) >= 2:
                headers = [c.strip() for c in table_lines[0].split("|") if c.strip()]
                rows = [
                    [c.strip() for c in row.split("|") if c.strip()]
                    for row in table_lines[2:]  # skip separator row
                    if row.strip() and not re.match(r"^\|[-| ]+\|$", row.strip())
                ]
                tables.append(TableData(caption=None, headers=headers, rows=rows))
            table_lines = []

    raw_text = re.sub(r"[#*`>|-]", " ", body_text)

    return GovernmentDocument(
        document_id=document_id, title=title, department=department,
        document_type=doc_type, status=status, publication_date=pub_date,
        last_updated=last_updated, audience=audience, topics=topics,
        version=version, supersedes=supersedes,
        related_documents=related_documents,
        sections=sections, tables=tables,
        keywords=_extract_keywords(raw_text),
        quality_flags=[], raw_text=raw_text,
        source_file=source_file, source_format="markdown",
    )


# ---------------------------------------------------------------------------
# Plain text extractor
# ---------------------------------------------------------------------------

def _extract_txt(content: str, source_file: str) -> GovernmentDocument:
    lines = content.splitlines()

    # Grab simple key: value metadata from the top block (first 15 lines)
    meta: dict = {}
    body_start = 0
    for i, line in enumerate(lines[:15]):
        match = re.match(r"^([A-Za-z _\-]+):\s+(.+)", line)
        if match:
            meta[match.group(1).strip().lower().replace(" ", "_")] = match.group(2).strip()
            body_start = i + 1

    document_id = meta.get("document_id", Path(source_file).stem.upper())
    title = meta.get("title") or (lines[0].strip() if lines else Path(source_file).stem)
    department = meta.get("department")
    doc_type = meta.get("document_type") or meta.get("type")
    status = meta.get("status")
    pub_date = meta.get("published") or meta.get("publication_date")
    last_updated = meta.get("last_updated")
    audience = meta.get("audience")
    topics = [t.strip() for t in meta.get("topics", "").split(",") if t.strip()]

    # Parse sections: lines in ALL CAPS or numbered headings (e.g. "1. Introduction")
    sections: List[Section] = []
    current_heading = ""
    current_level = 2
    current_body: List[str] = []

    heading_pattern = re.compile(r"^(\d+\.[\d.]?\s+.+|[A-Z][A-Z\s]{4,})$")

    for line in lines[body_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if heading_pattern.match(stripped) and len(stripped) < 80:
            if current_heading:
                sections.append(Section(
                    heading=current_heading,
                    level=current_level,
                    body=" ".join(current_body).strip(),
                ))
            current_heading = stripped
            current_level = 2
            current_body = []
        else:
            current_body.append(stripped)

    if current_heading:
        sections.append(Section(
            heading=current_heading,
            level=current_level,
            body=" ".join(current_body).strip(),
        ))

    return GovernmentDocument(
        document_id=document_id, title=title, department=department,
        document_type=doc_type, status=status, publication_date=pub_date,
        last_updated=last_updated, audience=audience, topics=topics,
        version=None, supersedes=None, related_documents=[],
        sections=sections, tables=[],
        keywords=_extract_keywords(content),
        quality_flags=[], raw_text=content,
        source_file=source_file, source_format="txt",
    )


# ---------------------------------------------------------------------------
# Public entry point — load all documents from a directory
# ---------------------------------------------------------------------------

def load_all_documents(folder: str) -> List[GovernmentDocument]:
    """Parse every HTML / Markdown / TXT file in folder and return documents."""
    docs: List[GovernmentDocument] = []
    for path in sorted(Path(folder).iterdir()):
        try:
            text = path.read_text(encoding="utf-8")
            suffix = path.suffix.lower()
            if suffix == ".html":
                docs.append(_extract_html(text, path.name))
            elif suffix in (".md", ".markdown"):
                docs.append(_extract_markdown(text, path.name))
            elif suffix == ".txt":
                docs.append(_extract_txt(text, path.name))
        except Exception as exc:
            print(f"[extractor] Skipping {path.name}: {exc}")
    return docs
