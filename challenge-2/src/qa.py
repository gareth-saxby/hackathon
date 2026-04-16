"""
Passage retrieval and data quality detection.
Challenge 2: Unlocking the Dark Data — DSIT AI Engineering Lab Hackathon 2026
"""

import re
from datetime import date, datetime
from typing import List, Optional

from .schema import (
    GovernmentDocument,
    STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION, DUPLICATE,
)
from .indexer import DocumentIndex, SearchResult


# ---------------------------------------------------------------------------
# Data quality detection — run once after extraction
# ---------------------------------------------------------------------------

def detect_quality_flags(
    docs: List[GovernmentDocument],
    index: Optional[DocumentIndex] = None,
    duplicate_threshold: float = 0.85,
) -> None:
    """Mutates each document's quality_flags list in place."""

    # Build lookup: document_id -> doc
    by_id = {d.document_id: d for d in docs}

    # Build set of superseded IDs from docs that declare supersedes
    superseded_ids = set()
    for doc in docs:
        if doc.supersedes:
            # supersedes field may contain "DOC-HB-002 v1.4 (2023-07-01)" — extract ID
            match = re.match(r"(DOC-[A-Z]+-\d+)", doc.supersedes)
            if match:
                superseded_ids.add(match.group(1))

    today = date.today()

    for doc in docs:
        flags = set(doc.quality_flags)

        # MISSING_METADATA
        if not doc.title or not doc.department or not doc.publication_date:
            flags.add(MISSING_METADATA)

        # STALE: status is current but last_updated is over 12 months ago
        if doc.status and doc.status.lower() == "current" and doc.last_updated:
            try:
                raw = doc.last_updated
                if isinstance(raw, date):
                    updated = raw
                else:
                    updated = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
                months_old = (today.year - updated.year) * 12 + (today.month - updated.month)
                if months_old > 12:
                    flags.add(STALE)
            except (ValueError, TypeError):
                pass

        # SUPERSEDED: another doc supersedes this one
        if doc.document_id in superseded_ids:
            flags.add(SUPERSEDED)

        doc.quality_flags = sorted(flags)

    # CONTRADICTION: scan for conflicting capital threshold values across docs.
    # Matches: £16,000 capital / 16000 savings / GBP 16,000 capital
    #
    # A single document legitimately lists multiple thresholds for different
    # circumstances (e.g. £16,000 general / £6,000 care home in DOC-HB-001).
    # That is NOT a contradiction.  A contradiction only exists when two or more
    # documents each state DIFFERENT values and no single document acts as the
    # comprehensive reference that covers all of them.
    threshold_pattern = re.compile(
        r"(?:£|GBP\s*)?([\d,]+)\s*(?:pounds?)?\s*(capital|savings)",
        re.IGNORECASE,
    )
    # doc_value_sets: doc_id -> set of distinct threshold values found in that doc
    doc_value_sets: dict = {}
    for doc in docs:
        found: set = set()
        for match in threshold_pattern.finditer(doc.raw_text):
            val = match.group(1).replace(",", "")
            found.add(val)
        if found:
            doc_value_sets[doc.document_id] = found

    if doc_value_sets:
        all_values: set = set().union(*doc_value_sets.values())
        if len(all_values) > 1:
            # A "comprehensive" doc is one whose value set equals the full corpus set —
            # it is the authoritative reference explaining all variants, not a contradiction.
            docs_with_all = {d for d, v in doc_value_sets.items() if v == all_values}
            if not docs_with_all:
                # No single doc covers all values → genuine cross-document contradiction.
                for doc_id in doc_value_sets:
                    if doc_id in by_id and CONTRADICTION not in by_id[doc_id].quality_flags:
                        by_id[doc_id].quality_flags.append(CONTRADICTION)

    # DUPLICATE: near-identical documents detected by cosine similarity
    if index is not None:
        duplicate_pairs = index.find_duplicates(threshold=duplicate_threshold)
        for doc_id_a, doc_id_b, _sim in duplicate_pairs:
            for doc_id in (doc_id_a, doc_id_b):
                if doc_id in by_id and DUPLICATE not in by_id[doc_id].quality_flags:
                    by_id[doc_id].quality_flags.append(DUPLICATE)


# ---------------------------------------------------------------------------
# Q&A: return the best matching passage for a natural language question
# ---------------------------------------------------------------------------

def ask(query: str, index: DocumentIndex) -> Optional[SearchResult]:
    """Return the single best matching passage for a query."""
    results = index.search(query, top_n=1)
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Quality summary across the whole corpus
# ---------------------------------------------------------------------------

def quality_summary(docs: List[GovernmentDocument], index: Optional[DocumentIndex] = None) -> dict:
    summary = {STALE: [], SUPERSEDED: [], MISSING_METADATA: [], CONTRADICTION: [], DUPLICATE: []}
    for doc in docs:
        for flag in doc.quality_flags:
            if flag in summary:
                summary[flag].append({
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "source_file": doc.source_file,
                })

    # Attach duplicate pairs for richer UI display
    if index is not None:
        summary["_duplicate_pairs"] = index.find_duplicates(threshold=0.85)

    return summary
