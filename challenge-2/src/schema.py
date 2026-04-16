"""
schema.py — GovernmentDocument dataclass and quality flag types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class QualityFlag(str, Enum):
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    MISSING_METADATA = "MISSING_METADATA"
    CONTRADICTION = "CONTRADICTION"


@dataclass
class Section:
    heading: str
    level: int
    body: str


@dataclass
class Table:
    caption: Optional[str]
    headers: List[str]
    rows: List[List[str]]


@dataclass
class GovernmentDocument:
    document_id: str
    title: str
    department: Optional[str] = None
    document_type: Optional[str] = None
    status: Optional[str] = None          # current | draft | superseded
    publication_date: Optional[str] = None
    last_updated: Optional[str] = None
    audience: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    version: Optional[str] = None
    supersedes: Optional[str] = None
    related_documents: List[str] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    quality_flags: List[QualityFlag] = field(default_factory=list)
    source_file: str = ""
    source_format: str = ""  # html | markdown | txt

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
            "quality_flags": [f.value for f in self.quality_flags],
            "source_file": self.source_file,
            "source_format": self.source_format,
        }

    @staticmethod
    def from_dict(data: dict) -> "GovernmentDocument":
        doc = GovernmentDocument(
            document_id=data.get("document_id", ""),
            title=data.get("title", ""),
            department=data.get("department"),
            document_type=data.get("document_type"),
            status=data.get("status"),
            publication_date=data.get("publication_date"),
            last_updated=data.get("last_updated"),
            audience=data.get("audience"),
            topics=data.get("topics", []),
            version=data.get("version"),
            supersedes=data.get("supersedes"),
            related_documents=data.get("related_documents", []),
            sections=[
                Section(
                    heading=s["heading"],
                    level=s["level"],
                    body=s["body"],
                )
                for s in data.get("sections", [])
            ],
            tables=[
                Table(
                    caption=t.get("caption"),
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                )
                for t in data.get("tables", [])
            ],
            keywords=data.get("keywords", []),
            quality_flags=[
                QualityFlag(f) for f in data.get("quality_flags", [])
                if f in QualityFlag._value2member_map_
            ],
            source_file=data.get("source_file", ""),
            source_format=data.get("source_format", ""),
        )
        return doc
