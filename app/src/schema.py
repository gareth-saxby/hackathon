from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


QualityFlag = Literal["STALE", "SUPERSEDED", "MISSING_METADATA", "CONTRADICTION"]
SourceFormat = Literal["html", "markdown", "txt"]
DocumentStatus = Literal["current", "draft", "superseded"]


@dataclass
class Section:
    heading: str
    level: int
    body: str


@dataclass
class Table:
    caption: str | None
    headers: list[str]
    rows: list[list[str]]


@dataclass
class GovernmentDocument:
    document_id: str
    title: str
    department: str | None
    document_type: str | None
    status: DocumentStatus | None
    publication_date: str | None
    last_updated: str | None
    audience: str | None
    topics: list[str]
    version: str | None
    supersedes: str | None
    related_documents: list[str]
    sections: list[Section]
    tables: list[Table]
    keywords: list[str]
    quality_flags: list[QualityFlag]
    source_file: str
    source_format: SourceFormat

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
            "sections": [{"heading": s.heading, "level": s.level, "body": s.body} for s in self.sections],
            "tables": [{"caption": t.caption, "headers": t.headers, "rows": t.rows} for t in self.tables],
            "keywords": self.keywords,
            "quality_flags": self.quality_flags,
            "source_file": self.source_file,
            "source_format": self.source_format,
        }
