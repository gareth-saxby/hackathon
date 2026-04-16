"""
Document schema for extracted government documents.
Challenge 2: Unlocking the Dark Data — DSIT AI Engineering Lab Hackathon 2026
"""

from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Quality flag constants
# ---------------------------------------------------------------------------

STALE = "STALE"                         # status=current but last_updated > 12 months
SUPERSEDED = "SUPERSEDED"               # another doc supersedes this one
MISSING_METADATA = "MISSING_METADATA"   # title / department / publication_date absent
CONTRADICTION = "CONTRADICTION"         # same policy value differs across docs
DUPLICATE = "DUPLICATE"                 # near-identical content found in another document


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

@dataclass
class TableData:
    caption: Optional[str]
    headers: List[str]
    rows: List[List[str]]


@dataclass
class Section:
    heading: str
    level: int   # 1=h1, 2=h2, 3=h3
    body: str


# ---------------------------------------------------------------------------
# Main document schema
# ---------------------------------------------------------------------------

@dataclass
class GovernmentDocument:
    document_id: str
    title: str
    department: Optional[str]
    document_type: Optional[str]
    status: Optional[str]
    publication_date: Optional[str]
    last_updated: Optional[str]
    audience: Optional[str]
    topics: List[str]
    version: Optional[str]
    supersedes: Optional[str]
    related_documents: List[str]
    sections: List[Section]
    tables: List[TableData]
    keywords: List[str]
    quality_flags: List[str]
    raw_text: str
    source_file: str
    source_format: str   # html | markdown | txt

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "department": self.department,
            "document_type": self.document_type,
            "status": self.status,
            "publication_date": self.publication_date,
            "last_updated": self.last_updated,
            "audience": self.audience,
            "topics": self.topics,
            "version": self.version,
            "supersedes": self.supersedes,
            "related_documents": self.related_documents,
            "sections": [
                {"heading": s.heading, "level": s.level, "body": s.body}
                for s in self.sections
            ],
            "tables": [
                {"caption": t.caption, "headers": t.headers, "rows": t.rows}
                for t in self.tables
            ],
            "keywords": self.keywords,
            "quality_flags": self.quality_flags,
            "raw_text": self.raw_text,
            "source_file": self.source_file,
            "source_format": self.source_format,
        }
