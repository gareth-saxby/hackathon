"""
test_integration.py — End-to-end tests against the real 20-document corpus.

These tests are marked `integration` and can be run separately:
    pytest -m integration

They require the structured data files to exist at:
    challenge-info/data/structured_files/
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.extractor import extract_all
from src.indexer import DocumentIndex
from src.qa import ask
from src.schema import QualityFlag

pytestmark = pytest.mark.integration

DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "challenge-info"
    / "data"
    / "structured_files"
)


@pytest.fixture(scope="module")
def corpus():
    if not DATA_DIR.exists():
        pytest.skip(f"Data directory not found: {DATA_DIR}")
    return extract_all(DATA_DIR)


@pytest.fixture(scope="module")
def index(corpus):
    idx = DocumentIndex()
    idx.build(corpus)
    return idx


# ---------------------------------------------------------------------------
# Corpus completeness
# ---------------------------------------------------------------------------

class TestCorpusCompleteness:
    def test_all_20_documents_loaded(self, corpus):
        assert len(corpus) == 20

    def test_housing_and_smallbusiness_docs_present(self, corpus):
        hb_ids = [d.document_id for d in corpus if d.document_id.startswith("DOC-HB-")]
        sb_ids = [d.document_id for d in corpus if d.document_id.startswith("DOC-SB-")]
        assert len(hb_ids) == 10
        assert len(sb_ids) == 10

    def test_all_docs_have_document_id(self, corpus):
        for doc in corpus:
            assert doc.document_id, f"Missing document_id in {doc.source_file}"

    def test_all_docs_have_title(self, corpus):
        for doc in corpus:
            assert doc.title, f"Missing title in {doc.document_id}"

    def test_all_docs_have_at_least_one_section(self, corpus):
        for doc in corpus:
            assert doc.sections, f"No sections in {doc.document_id}"

    def test_expected_doc_ids_present(self, corpus):
        ids = {d.document_id for d in corpus}
        for i in range(1, 11):
            assert f"DOC-HB-{i:03d}" in ids, f"DOC-HB-{i:03d} missing"
            assert f"DOC-SB-{i:03d}" in ids, f"DOC-SB-{i:03d} missing"

    def test_html_markdown_txt_formats_all_parsed(self, corpus):
        formats = {d.source_format for d in corpus}
        assert "html" in formats
        assert "markdown" in formats
        assert "txt" in formats


# ---------------------------------------------------------------------------
# Quality flags detected in real corpus (FR-10 to FR-13)
# ---------------------------------------------------------------------------

class TestCorpusQualityFlags:
    def test_at_least_one_stale_doc_detected(self, corpus):
        stale = [d for d in corpus if QualityFlag.STALE in d.quality_flags]
        assert stale, "Expected at least one STALE document in the real corpus"

    def test_at_least_one_superseded_doc_detected(self, corpus):
        sup = [d for d in corpus if QualityFlag.SUPERSEDED in d.quality_flags]
        assert sup, "Expected at least one SUPERSEDED document in the real corpus"

    def test_at_least_one_missing_metadata_doc(self, corpus):
        missing = [d for d in corpus if QualityFlag.MISSING_METADATA in d.quality_flags]
        assert missing, "Expected at least one MISSING_METADATA document in the real corpus"

    def test_quality_flag_values_are_valid(self, corpus):
        valid = {f.value for f in QualityFlag}
        for doc in corpus:
            for flag in doc.quality_flags:
                assert flag.value in valid


# ---------------------------------------------------------------------------
# Search quality (FR-06, FR-07, FR-08)
# ---------------------------------------------------------------------------

class TestSearchQuality:
    def test_search_returns_results(self, index):
        results = index.search("housing benefit eligibility")
        assert len(results) > 0

    def test_housing_benefit_query_returns_hb_doc(self, index):
        results = index.search("housing benefit eligibility capital limit")
        doc_ids = [r.document_id for r in results]
        hb_docs = [d for d in doc_ids if d.startswith("DOC-HB-")]
        assert hb_docs, "Expected at least one HB document in results"

    def test_small_business_query_returns_sb_doc(self, index):
        results = index.search("register business companies house corporation tax")
        doc_ids = [r.document_id for r in results]
        sb_docs = [d for d in doc_ids if d.startswith("DOC-SB-")]
        assert sb_docs, "Expected at least one SB document in results"

    def test_result_has_required_fields(self, index):
        results = index.search("housing benefit")
        r = results[0]
        assert r.document_id
        assert r.title
        assert r.section_heading
        assert r.passage
        assert r.score > 0

    def test_topic_filter_narrows_results(self, index):
        all_results = index.search("housing benefit")
        topics = index.get_all_topics()
        if "housing-benefit" in topics:
            filtered = index.search("housing benefit", topic_filter="housing-benefit")
            assert len(filtered) <= len(all_results)

    def test_passage_fits_within_400_chars(self, index):
        results = index.search("housing benefit", top_n=10)
        for r in results:
            assert len(r.passage) <= 420  # small buffer for ellipsis

    def test_quality_flags_propagated_to_results(self, index, corpus):
        flagged_ids = {d.document_id for d in corpus if d.quality_flags}
        results = index.search("housing benefit", top_n=20)
        # If any flagged doc appears in results its flags should be populated
        for r in results:
            if r.document_id in flagged_ids:
                assert r.quality_flags


# ---------------------------------------------------------------------------
# QA ask() against real corpus
# ---------------------------------------------------------------------------

class TestQaAsk:
    def test_ask_housing_benefit_returns_answer(self, index):
        answer = ask(index, "What is the capital limit for housing benefit?")
        assert answer is not None

    def test_ask_answer_passage_not_empty(self, index):
        answer = ask(index, "minimum wage rate")
        assert answer is not None
        assert answer.passage

    def test_ask_has_confidence_field(self, index):
        answer = ask(index, "how to register as self employed")
        assert answer is not None
        assert answer.confidence in ("high", "medium", "low")
