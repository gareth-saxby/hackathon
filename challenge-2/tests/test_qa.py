"""
Tests for src/qa.py — quality flag detection, ask(), quality_summary().
"""
import pytest
from datetime import date

from src.qa import detect_quality_flags, ask, quality_summary
from src.indexer import DocumentIndex
from src.schema import (
    GovernmentDocument, Section,
    STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION, DUPLICATE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_doc(
    doc_id="DOC-QA-001",
    title="Test Document",
    department="Test Dept",
    status="current",
    publication_date="2025-01-01",
    last_updated="2025-03-01",
    supersedes=None,
    sections=None,
    raw_text="This is generic test content about benefits.",
    topics=None,
):
    return GovernmentDocument(
        document_id=doc_id,
        title=title,
        department=department,
        document_type="guidance",
        status=status,
        publication_date=publication_date,
        last_updated=last_updated,
        audience="Staff",
        topics=topics or [],
        version=None,
        supersedes=supersedes,
        related_documents=[],
        sections=sections or [Section("Overview", 2, raw_text)],
        tables=[],
        keywords=[],
        quality_flags=[],
        raw_text=raw_text,
        source_file=f"{doc_id}.html",
        source_format="html",
    )


# ---------------------------------------------------------------------------
# STALE flag
# ---------------------------------------------------------------------------

class TestStaleFlag:
    def test_stale_flagged_when_over_12_months(self):
        doc = make_doc(last_updated="2023-01-01", status="current")
        detect_quality_flags([doc])
        assert STALE in doc.quality_flags

    def test_stale_not_flagged_when_recent(self):
        doc = make_doc(last_updated="2025-10-01", status="current")
        detect_quality_flags([doc])
        assert STALE not in doc.quality_flags

    def test_stale_not_flagged_for_non_current_status(self):
        doc = make_doc(last_updated="2023-01-01", status="superseded")
        detect_quality_flags([doc])
        assert STALE not in doc.quality_flags

    def test_stale_not_flagged_when_last_updated_missing(self):
        doc = make_doc(last_updated=None, status="current")
        detect_quality_flags([doc])
        assert STALE not in doc.quality_flags


# ---------------------------------------------------------------------------
# SUPERSEDED flag
# ---------------------------------------------------------------------------

class TestSupersededFlag:
    def test_superseded_flagged_when_another_doc_supersedes_it(self):
        old_doc = make_doc("DOC-QA-001")
        new_doc = make_doc("DOC-QA-002", supersedes="DOC-QA-001")
        detect_quality_flags([old_doc, new_doc])
        assert SUPERSEDED in old_doc.quality_flags

    def test_superseding_doc_not_flagged_as_superseded(self):
        old_doc = make_doc("DOC-QA-001")
        new_doc = make_doc("DOC-QA-002", supersedes="DOC-QA-001")
        detect_quality_flags([old_doc, new_doc])
        assert SUPERSEDED not in new_doc.quality_flags

    def test_no_superseded_flag_when_no_cross_reference(self):
        doc = make_doc("DOC-QA-001")
        detect_quality_flags([doc])
        assert SUPERSEDED not in doc.quality_flags


# ---------------------------------------------------------------------------
# MISSING_METADATA flag
# ---------------------------------------------------------------------------

class TestMissingMetadataFlag:
    def test_flagged_when_title_missing(self):
        doc = make_doc(title="")
        detect_quality_flags([doc])
        assert MISSING_METADATA in doc.quality_flags

    def test_flagged_when_department_missing(self):
        doc = make_doc(department=None)
        detect_quality_flags([doc])
        assert MISSING_METADATA in doc.quality_flags

    def test_flagged_when_publication_date_missing(self):
        doc = make_doc(publication_date=None)
        detect_quality_flags([doc])
        assert MISSING_METADATA in doc.quality_flags

    def test_not_flagged_when_all_metadata_present(self):
        doc = make_doc()
        detect_quality_flags([doc])
        assert MISSING_METADATA not in doc.quality_flags


# ---------------------------------------------------------------------------
# CONTRADICTION flag
# ---------------------------------------------------------------------------

class TestContradictionFlag:
    def test_contradiction_flagged_when_thresholds_differ(self):
        doc_a = make_doc("DOC-QA-A", raw_text="Savings must be below £16,000 capital.")
        doc_b = make_doc("DOC-QA-B", raw_text="Savings must be below £6,000 capital.")
        detect_quality_flags([doc_a, doc_b])
        # At least one of the docs with conflicting values is flagged
        flagged = [d for d in [doc_a, doc_b] if CONTRADICTION in d.quality_flags]
        assert len(flagged) >= 1

    def test_contradiction_not_flagged_when_values_agree(self):
        doc_a = make_doc("DOC-QA-A", raw_text="Savings limit is £16,000 capital.")
        doc_b = make_doc("DOC-QA-B", raw_text="The capital limit is £16,000 savings.")
        detect_quality_flags([doc_a, doc_b])
        assert CONTRADICTION not in doc_a.quality_flags
        assert CONTRADICTION not in doc_b.quality_flags

    def test_intra_doc_multi_threshold_not_flagged(self):
        """A single doc listing multiple thresholds for different circumstances
        (e.g. £16,000 general / £6,000 care home) must NOT be flagged."""
        authoritative = make_doc(
            "DOC-QA-AUTH",
            raw_text=(
                "The general capital limit is £16,000 capital. "
                "If you are in a care home the limit is £6,000 capital."
            ),
        )
        other = make_doc(
            "DOC-QA-OTHER",
            raw_text="The general capital threshold is £16,000 capital.",
        )
        detect_quality_flags([authoritative, other])
        assert CONTRADICTION not in authoritative.quality_flags
        assert CONTRADICTION not in other.quality_flags


# ---------------------------------------------------------------------------
# Idempotency — running twice should not duplicate flags
# ---------------------------------------------------------------------------

class TestFlagIdempotency:
    def test_flags_not_duplicated_on_second_run(self):
        doc = make_doc(last_updated="2023-01-01", status="current")
        detect_quality_flags([doc])
        detect_quality_flags([doc])
        assert doc.quality_flags.count(STALE) == 1


# ---------------------------------------------------------------------------
# ask()
# ---------------------------------------------------------------------------

class TestAsk:
    def _make_index(self):
        docs = [
            make_doc("DOC-ASK-001", raw_text="Housing Benefit helps pay rent for low income claimants."),
            make_doc("DOC-ASK-002", raw_text="Self-employed workers must register for National Insurance."),
        ]
        return DocumentIndex(docs)

    def test_ask_returns_search_result_for_matching_query(self):
        from src.indexer import SearchResult
        index = self._make_index()
        result = ask("housing benefit rent", index)
        assert result is not None
        assert isinstance(result, SearchResult)

    def test_ask_returns_none_for_unrelated_query(self):
        index = self._make_index()
        result = ask("quantum computing spacecraft", index)
        assert result is None

    def test_ask_result_has_passage(self):
        index = self._make_index()
        result = ask("housing benefit rent", index)
        assert result is not None
        assert len(result.passage) > 0


# ---------------------------------------------------------------------------
# quality_summary()
# ---------------------------------------------------------------------------

class TestQualitySummary:
    def test_summary_keys_are_flag_constants(self):
        docs = [make_doc()]
        detect_quality_flags(docs)
        summary = quality_summary(docs)
        assert {STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION, DUPLICATE}.issubset(
            set(summary.keys())
        )

    def test_stale_doc_appears_in_summary(self):
        doc = make_doc(last_updated="2023-01-01", status="current")
        detect_quality_flags([doc])
        summary = quality_summary([doc])
        assert any(e["document_id"] == "DOC-QA-001" for e in summary[STALE])

    def test_clean_doc_absent_from_all_lists(self):
        doc = make_doc(last_updated="2025-10-01")
        detect_quality_flags([doc])
        summary = quality_summary([doc])
        for entries in summary.values():
            assert not any(e["document_id"] == "DOC-QA-001" for e in entries)

    def test_summary_entry_has_required_keys(self):
        doc = make_doc(last_updated="2023-01-01", status="current")
        detect_quality_flags([doc])
        summary = quality_summary([doc])
        entry = summary[STALE][0]
        assert "document_id" in entry
        assert "title" in entry
        assert "source_file" in entry
