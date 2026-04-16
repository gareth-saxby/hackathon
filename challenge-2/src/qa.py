"""
qa.py — Passage retrieval: given a question, return the single best matching passage.
No LLM required (NFR-01).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .indexer import DocumentIndex, SearchResult


@dataclass
class Answer:
    passage: str
    document_id: str
    title: str
    section_heading: str
    publication_date: Optional[str]
    status: Optional[str]
    quality_flags: list
    score: float

    @property
    def confidence(self) -> str:
        if self.score >= 0.3:
            return "high"
        if self.score >= 0.1:
            return "medium"
        return "low"


def ask(index: DocumentIndex, question: str) -> Optional[Answer]:
    """
    Return the single best passage from the index that answers *question*.
    Returns None if no relevant result is found.
    """
    results = index.search(question, top_n=1)
    if not results:
        return None
    r: SearchResult = results[0]
    return Answer(
        passage=r.passage,
        document_id=r.document_id,
        title=r.title,
        section_heading=r.section_heading,
        publication_date=r.publication_date,
        status=r.status,
        quality_flags=r.quality_flags,
        score=r.score,
    )
