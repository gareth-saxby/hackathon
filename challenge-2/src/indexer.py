"""
TF-IDF search index over extracted government documents.
Challenge 2: Unlocking the Dark Data — DSIT AI Engineering Lab Hackathon 2026
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .schema import GovernmentDocument


# ---------------------------------------------------------------------------
# Search result structure
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    document_id: str
    title: str
    department: Optional[str]
    status: Optional[str]
    publication_date: Optional[str]
    last_updated: Optional[str]
    source_file: str
    source_format: str          # html | markdown | txt | govuk-api
    section_heading: str
    passage: str
    score: float
    quality_flags: List[str]
    matching_terms: List[str] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        """True when this result came from the live GOV.UK API."""
        return self.source_format == "govuk-api"


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class DocumentIndex:
    def __init__(self, documents: List[GovernmentDocument]):
        self._docs = documents
        # Build one entry per section (finer-grained retrieval)
        self._entries: List[dict] = []
        for doc in documents:
            for section in doc.sections:
                combined = f"{doc.title} {section.heading} {section.body}"
                self._entries.append({
                    "doc": doc,
                    "section_heading": section.heading,
                    "passage": section.body,
                    "text": combined,
                })
            # If a doc has no sections, fall back to raw text
            if not doc.sections:
                self._entries.append({
                    "doc": doc,
                    "section_heading": "(full document)",
                    "passage": doc.raw_text[:1000],
                    "text": doc.raw_text,
                })

        corpus = [e["text"] for e in self._entries]
        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=10000,
        )
        self._ready = bool(corpus) and any(t.strip() for t in corpus)
        if self._ready:
            self._matrix = self._vectorizer.fit_transform(corpus)
            # Build one aggregated doc-level vector per unique document for duplicate detection
            self._doc_vectors: Dict[str, np.ndarray] = {}
            for i, entry in enumerate(self._entries):
                doc_id = entry["doc"].document_id
                vec = self._matrix[i].toarray()
                if doc_id in self._doc_vectors:
                    self._doc_vectors[doc_id] = self._doc_vectors[doc_id] + vec
                else:
                    self._doc_vectors[doc_id] = vec
        else:
            self._matrix = None
            self._doc_vectors = {}

    def search(
        self,
        query: str,
        top_n: int = 8,
        status_filter: Optional[str] = None,
        topic_filter: Optional[str] = None,
    ) -> List[SearchResult]:
        if not self._ready:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix).flatten()

        ranked = sorted(enumerate(scores), key=lambda x: -x[1])

        # Pre-compute which terms the query activates (for matching_terms)
        query_arr = query_vec.toarray()[0]
        feature_names = self._vectorizer.get_feature_names_out()
        query_term_indices = set(np.where(query_arr > 0)[0])

        results: List[SearchResult] = []
        seen_doc_ids: set = set()
        for idx, score in ranked:
            if score < 0.01:
                break
            entry = self._entries[idx]
            doc: GovernmentDocument = entry["doc"]

            if status_filter and (doc.status or "").lower() != status_filter.lower():
                continue
            if topic_filter and not any(
                topic_filter.lower() in t.lower() for t in doc.topics
            ):
                continue

            # Matching terms: query terms that also appear in this section
            entry_arr = self._matrix[idx].toarray()[0]
            entry_term_indices = set(np.where(entry_arr > 0)[0])
            overlap_indices = query_term_indices & entry_term_indices
            # Sort by document TF-IDF weight descending, keep top 8
            sorted_overlap = sorted(
                overlap_indices,
                key=lambda i: entry_arr[i],
                reverse=True,
            )[:8]
            matching = [feature_names[i] for i in sorted_overlap]

            results.append(SearchResult(
                document_id=doc.document_id,
                title=doc.title,
                department=doc.department,
                status=doc.status,
                publication_date=doc.publication_date,
                last_updated=doc.last_updated,
                source_file=doc.source_file,
                source_format=doc.source_format,
                section_heading=entry["section_heading"],
                passage=entry["passage"][:400],
                score=round(float(score), 4),
                quality_flags=doc.quality_flags,
                matching_terms=matching,
            ))

            if len(results) >= top_n:
                break

        return results

    def all_documents(self) -> List[GovernmentDocument]:
        return self._docs

    def find_duplicates(
        self, threshold: float = 0.85
    ) -> List[Tuple[str, str, float]]:
        """
        Return pairs of (doc_id_a, doc_id_b, similarity_score) where
        cosine similarity between aggregated document vectors >= threshold.
        Each pair is returned once (a < b lexicographically).
        """
        if not self._doc_vectors:
            return []

        doc_ids = list(self._doc_vectors.keys())
        vectors = np.vstack([self._doc_vectors[d] for d in doc_ids])

        # Normalise rows to unit length for cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # avoid div-by-zero for empty docs
        normed = vectors / norms

        sim_matrix = normed @ normed.T

        pairs: List[Tuple[str, str, float]] = []
        n = len(doc_ids)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i, j])
                if sim >= threshold:
                    pairs.append((doc_ids[i], doc_ids[j], round(sim, 4)))

        return sorted(pairs, key=lambda x: -x[2])


# ---------------------------------------------------------------------------
# Merged index helper
# ---------------------------------------------------------------------------

def build_merged(
    base_docs: List[GovernmentDocument],
    extra_docs: List[GovernmentDocument],
) -> DocumentIndex:
    """
    Return a new DocumentIndex built from *base_docs* + *extra_docs* combined.

    Used to blend local corpus documents with live GOV.UK API documents so
    that a single search ranks all passages on the same TF-IDF scale.

    Duplicate document_ids in *extra_docs* (vs *base_docs*) are skipped to
    avoid double-counting if the same GOV.UK page was already in the corpus.
    """
    existing_ids = {d.document_id for d in base_docs}
    deduped_extra = [d for d in extra_docs if d.document_id not in existing_ids]
    return DocumentIndex(base_docs + deduped_extra)
