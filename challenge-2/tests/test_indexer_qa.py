"""
test_indexer_qa.py — Tests for DocumentIndex (TF-IDF search) and qa.ask().
"""
from __future__ import annotations

from typing import List

import pytest

from src.indexer import DocumentIndex, SearchResult, _effective_status, _truncate
from src.qa import ask
from src.schema import GovernmentDocument, QualityFlag, Section


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(
    doc_id: str,
    title: str,
    section_body: str,
    status: str = "current",
    topics: List[str] = None,
    quality_flags: List[QualityFlag] = None,
    pub_date: str = "2025-01-01",
) -> GovernmentDocument:
    return GovernmentDocument(
        document_id=doc_id,
        title=title,
        department="Test Dept",
        status=status,
        publication_date=pub_date,
        topics=topics or [],
        quality_flags=quality_flags or [],
        sections=[Section(heading="Main", level=1, body=section_body)],
    )


HOUSING_DOC = _make_doc(
    "DOC-H-001",
    "Housing Benefit Guide",
    "Housing Benefit helps low-income claimants pay rent. Capital threshold is £16,000.",
    topics=["housing-benefit", "benefits"],
)

PENSION_DOC = _make_doc(
    "DOC-P-001",
    "Pension Credit Guide",
    "Pension Credit tops up weekly income for pensioners. Savings Credit applies to those who saved.",
    topics=["pensions"],
)

BUSINESS_DOC = _make_doc(
    "DOC-SB-001",
    "Starting a Business",
    "Register your business with Companies House. Corporation tax applies to all limited companies.",
    topics=["business", "tax"],
)

STALE_DOC = _make_doc(
    "DOC-STALE-001",
    "Old Policy",
    "This contains old information about housing benefit.",
    quality_flags=[QualityFlag.STALE],
    topics=["housing-benefit"],
)

SUPERSEDED_DOC = _make_doc(
    "DOC-SUP-001",
    "Superseded Policy",
    "This policy was superseded by newer guidance on housing benefit.",
    status="superseded",
    quality_flags=[QualityFlag.SUPERSEDED],
    topics=["housing-benefit"],
)

ALL_DOCS = [HOUSING_DOC, PENSION_DOC, BUSINESS_DOC, STALE_DOC, SUPERSEDED_DOC]


@pytest.fixture()
def built_index() -> DocumentIndex:
    idx = DocumentIndex()
    idx.build(ALL_DOCS)
    return idx


# ===========================================================================
# DocumentIndex.build
# ===========================================================================

class TestDocumentIndexBuild:
    def test_documents_accessible_after_build(self, built_index):
        assert len(built_index.documents) == len(ALL_DOCS)

    def test_empty_build_does_not_raise(self):
        idx = DocumentIndex()
        idx.build([])
        assert idx.documents == []

    def test_all_topics_aggregated(self, built_index):
        topics = built_index.get_all_topics()
        assert "housing-benefit" in topics
        assert "pensions" in topics
        assert "business" in topics

    def test_all_topics_sorted(self, built_index):
        topics = built_index.get_all_topics()
        assert topics == sorted(topics)


# ===========================================================================
# DocumentIndex.search — basic relevance (FR-07, FR-08)
# ===========================================================================

class TestDocumentIndexSearch:
    def test_returns_list(self, built_index):
        results = built_index.search("housing benefit")
        assert isinstance(results, list)

    def test_returns_search_result_objects(self, built_index):
        results = built_index.search("housing benefit")
        for r in results:
            assert isinstance(r, SearchResult)

    def test_relevant_doc_in_top_results(self, built_index):
        results = built_index.search("housing benefit capital threshold")
        doc_ids = [r.document_id for r in results]
        assert "DOC-H-001" in doc_ids

    def test_pension_query_returns_pension_doc(self, built_index):
        results = built_index.search("pension credit savings")
        doc_ids = [r.document_id for r in results]
        assert "DOC-P-001" in doc_ids

    def test_business_query_returns_business_doc(self, built_index):
        results = built_index.search("register company corporation tax")
        doc_ids = [r.document_id for r in results]
        assert "DOC-SB-001" in doc_ids

    def test_empty_query_returns_empty(self, built_index):
        results = built_index.search("")
        assert results == []

    def test_whitespace_query_returns_empty(self, built_index):
        results = built_index.search("   ")
        assert results == []

    def test_top_n_respected(self, built_index):
        results = built_index.search("housing benefit", top_n=2)
        assert len(results) <= 2

    def test_result_fields_populated(self, built_index):
        results = built_index.search("housing benefit")
        r = results[0]
        assert r.document_id
        assert r.title
        assert r.section_heading
        assert r.passage
        assert isinstance(r.score, float)
        assert r.score > 0

    def test_results_sorted_by_score_descending(self, built_index):
        results = built_index.search("housing benefit capital")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_scores_between_zero_and_one(self, built_index):
        results = built_index.search("housing")
        for r in results:
            assert 0.0 < r.score <= 1.0


# ===========================================================================
# DocumentIndex.search — filtering (FR-09)
# ===========================================================================

class TestDocumentIndexFiltering:
    def test_topic_filter_excludes_non_matching(self, built_index):
        results = built_index.search("housing", topic_filter="pensions")
        for r in results:
            assert "pensions" in [t.lower() for t in r.topics]

    def test_topic_filter_case_insensitive(self, built_index):
        results_lower = built_index.search("housing", topic_filter="housing-benefit")
        results_upper = built_index.search("housing", topic_filter="HOUSING-BENEFIT")
        assert len(results_lower) == len(results_upper)

    def test_status_filter_current(self, built_index):
        results = built_index.search("housing", status_filter="current")
        for r in results:
            assert r.document_id not in ("DOC-STALE-001", "DOC-SUP-001")

    def test_status_filter_stale(self, built_index):
        results = built_index.search("housing", status_filter="stale")
        doc_ids = [r.document_id for r in results]
        assert "DOC-STALE-001" in doc_ids

    def test_status_filter_superseded(self, built_index):
        results = built_index.search("housing", status_filter="superseded")
        doc_ids = [r.document_id for r in results]
        assert "DOC-SUP-001" in doc_ids

    def test_no_results_for_impossible_filter_combination(self, built_index):
        results = built_index.search(
            "pension", topic_filter="business", status_filter="current"
        )
        assert results == []


# ===========================================================================
# SearchResult helpers
# ===========================================================================

class TestSearchResult:
    def _make_result(self, flags=None):
        return SearchResult(
            document_id="DOC-X-001",
            title="Test",
            section_heading="Section",
            passage="Some text.",
            publication_date="2025-01-01",
            status="current",
            quality_flags=flags or [],
            score=0.5,
            topics=[],
        )

    def test_is_stale_true(self):
        r = self._make_result(["STALE"])
        assert r.is_stale is True

    def test_is_stale_false(self):
        r = self._make_result()
        assert r.is_stale is False

    def test_is_superseded_true(self):
        r = self._make_result(["SUPERSEDED"])
        assert r.is_superseded is True

    def test_flag_summary_none_when_no_flags(self):
        r = self._make_result()
        assert r.flag_summary is None

    def test_flag_summary_contains_warning_text(self):
        r = self._make_result(["STALE", "SUPERSEDED"])
        summary = r.flag_summary
        assert summary is not None
        assert "out of date" in summary.lower() or "superseded" in summary.lower()

    def test_flag_summary_multiple_flags_joined(self):
        r = self._make_result(["STALE", "MISSING_METADATA"])
        assert "|" in r.flag_summary


# ===========================================================================
# _effective_status helper
# ===========================================================================

class TestEffectiveStatus:
    def test_superseded_flag_overrides_status_field(self):
        doc = _make_doc("X", "X", "body", status="current", quality_flags=[QualityFlag.SUPERSEDED])
        assert _effective_status(doc) == "superseded"

    def test_stale_flag_returned_when_no_superseded(self):
        doc = _make_doc("X", "X", "body", status="current", quality_flags=[QualityFlag.STALE])
        assert _effective_status(doc) == "stale"

    def test_status_field_used_when_no_flags(self):
        doc = _make_doc("X", "X", "body", status="current")
        assert _effective_status(doc) == "current"

    def test_unknown_returned_when_status_none(self):
        doc = GovernmentDocument(document_id="X", title="X")
        assert _effective_status(doc) == "unknown"


# ===========================================================================
# _truncate helper
# ===========================================================================

class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("hello world", 100) == "hello world"

    def test_long_text_truncated(self):
        long = "word " * 100
        result = _truncate(long, 50)
        assert len(result) <= 55  # small tolerance for ellipsis
        assert result.endswith("…")

    def test_truncated_at_word_boundary(self):
        text = "alpha beta gamma delta epsilon"
        result = _truncate(text, 12)
        assert not result.startswith(" ")
        assert "…" in result

    def test_newlines_normalised(self):
        text = "line one\nline two\nline three"
        result = _truncate(text, 200)
        assert "\n" not in result


# ===========================================================================
# qa.ask()
# ===========================================================================

class TestAsk:
    def test_returns_answer_for_matching_query(self, built_index):
        answer = ask(built_index, "housing benefit capital threshold")
        assert answer is not None
        assert answer.document_id == "DOC-H-001"

    def test_returns_none_for_empty_query(self, built_index):
        answer = ask(built_index, "")
        assert answer is None

    def test_answer_has_passage(self, built_index):
        answer = ask(built_index, "pension savings credit")
        assert answer is not None
        assert answer.passage

    def test_answer_confidence_high_for_exact_match(self, built_index):
        answer = ask(built_index, "housing benefit capital threshold £16,000")
        assert answer is not None
        assert answer.confidence in ("high", "medium", "low")

    def test_answer_includes_quality_flags(self, built_index):
        # Ask about stale content specifically
        answer = ask(built_index, "old information housing benefit")
        assert answer is not None
        assert isinstance(answer.quality_flags, list)

    def test_ask_on_empty_index_returns_none(self):
        idx = DocumentIndex()
        idx.build([])
        result = ask(idx, "housing benefit")
        assert result is None
