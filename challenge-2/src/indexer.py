"""
indexer.py — TF-IDF search index over extracted GovernmentDocument sections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .schema import GovernmentDocument, QualityFlag


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    document_id: str
    title: str
    section_heading: str
    passage: str
    publication_date: Optional[str]
    status: Optional[str]
    quality_flags: List[str]
    score: float
    topics: List[str]

    @property
    def is_stale(self) -> bool:
        return QualityFlag.STALE.value in self.quality_flags

    @property
    def is_superseded(self) -> bool:
        return QualityFlag.SUPERSEDED.value in self.quality_flags

    @property
    def flag_summary(self) -> Optional[str]:
        if not self.quality_flags:
            return None
        labels = {
            "STALE": "⚠️ This document may be out of date",
            "SUPERSEDED": "⚠️ This document may be superseded",
            "MISSING_METADATA": "⚠️ Incomplete metadata",
            "CONTRADICTION": "⚠️ Possible contradiction with another document",
        }
        msgs = [labels[f] for f in self.quality_flags if f in labels]
        return " | ".join(msgs) if msgs else None


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class DocumentIndex:
    """Build and query a TF-IDF index over document sections."""

    def __init__(self) -> None:
        self._docs: List[GovernmentDocument] = []
        self._chunks: List[dict] = []   # {doc_idx, section_idx, text}
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matrix = None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, documents: List[GovernmentDocument]) -> None:
        """Index all sections from *documents*."""
        self._docs = documents
        self._chunks = []

        for doc_idx, doc in enumerate(documents):
            for sec_idx, section in enumerate(doc.sections):
                text = f"{section.heading} {section.body}".strip()
                if text:
                    self._chunks.append(
                        {
                            "doc_idx": doc_idx,
                            "sec_idx": sec_idx,
                            "text": text,
                        }
                    )

        if not self._chunks:
            return

        corpus = [c["text"] for c in self._chunks]
        self._vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            ngram_range=(1, 2),
            max_df=0.95,
            min_df=1,
            sublinear_tf=True,
        )
        self._matrix = self._vectorizer.fit_transform(corpus)

    # ------------------------------------------------------------------
    # Search (FR-07, FR-08, FR-09)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_n: int = 10,
        topic_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Return the top-N most relevant passages matching *query*.

        Parameters
        ----------
        query        : free-text search string
        top_n        : max results to return
        topic_filter : if set, only include documents whose topics contain this value
        status_filter: if set, only include documents with this status
                       (one of: "current", "stale", "superseded")
        """
        if self._vectorizer is None or self._matrix is None or not query.strip():
            return []

        q_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self._matrix).flatten()

        # Rank all chunks
        ranked_indices = scores.argsort()[::-1]

        results: List[SearchResult] = []
        seen_sections: set = set()

        for idx in ranked_indices:
            if scores[idx] == 0:
                break
            chunk = self._chunks[idx]
            doc = self._docs[chunk["doc_idx"]]
            section = doc.sections[chunk["sec_idx"]]

            # Deduplicate identical section from same doc
            key = (doc.document_id, chunk["sec_idx"])
            if key in seen_sections:
                continue
            seen_sections.add(key)

            # FR-09: apply filters
            if topic_filter and topic_filter.lower() not in [
                t.lower() for t in doc.topics
            ]:
                continue
            if status_filter:
                effective_status = _effective_status(doc)
                if effective_status.lower() != status_filter.lower():
                    continue

            results.append(
                SearchResult(
                    document_id=doc.document_id,
                    title=doc.title,
                    section_heading=section.heading,
                    passage=_truncate(section.body, 400),
                    publication_date=doc.publication_date,
                    status=doc.status,
                    quality_flags=[f.value for f in doc.quality_flags],
                    score=float(scores[idx]),
                    topics=doc.topics,
                )
            )

            if len(results) >= top_n:
                break

        return results

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def documents(self) -> List[GovernmentDocument]:
        return self._docs

    def get_all_topics(self) -> List[str]:
        topics: set = set()
        for doc in self._docs:
            topics.update(t.lower() for t in doc.topics if t)
        return sorted(topics)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_chars: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"


def _effective_status(doc: GovernmentDocument) -> str:
    """Return a display status considering quality flags."""
    flags = {f.value for f in doc.quality_flags}
    if "SUPERSEDED" in flags:
        return "superseded"
    if "STALE" in flags:
        return "stale"
    return (doc.status or "unknown").lower()
