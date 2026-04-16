"""
Tests for src/indexer.py — TF-IDF search index.
"""
import pytest
from src.indexer import DocumentIndex, SearchResult
from src.schema import GovernmentDocument, Section


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_doc(doc_id, title, sections, status="current", topics=None, department=None):
    return GovernmentDocument(
        document_id=doc_id,
        title=title,
        department=department or "Test Dept",
        document_type="guidance",
        status=status,
        publication_date="2025-01-01",
        last_updated="2025-06-01",
        audience="Staff",
        topics=topics or [],
        version=None,
        supersedes=None,
        related_documents=[],
        sections=sections,
        tables=[],
        keywords=[],
        quality_flags=[],
        raw_text=" ".join(s.body for s in sections),
        source_file=f"{doc_id}.html",
        source_format="html",
    )


@pytest.fixture
def sample_index():
    docs = [
        make_doc("DOC-001", "Housing Benefit Eligibility", [
            Section("Overview", 2, "Housing Benefit helps pay rent for low income claimants."),
            Section("Eligibility", 2, "You must have savings below sixteen thousand pounds."),
        ], topics=["housing-benefit"]),
        make_doc("DOC-002", "Starting a Business", [
            Section("Registration", 2, "All businesses must register with HMRC for tax purposes."),
            Section("VAT", 2, "Register for VAT if turnover exceeds ninety thousand pounds."),
        ], topics=["business", "self-employment"]),
        make_doc("DOC-003", "Council Tax Reduction", [
            Section("Introduction", 2, "Council Tax Reduction replaced Council Tax Benefit in 2013."),
        ], status="superseded", topics=["council-tax"]),
    ]
    return DocumentIndex(docs)


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------

class TestDocumentIndexConstruction:
    def test_index_created_without_error(self, sample_index):
        assert sample_index is not None

    def test_all_documents_stored(self, sample_index):
        assert len(sample_index.all_documents()) == 3

    def test_doc_with_no_sections_indexed(self):
        doc = make_doc("DOC-NOSEC", "No Sections Doc", sections=[])
        index = DocumentIndex([doc])
        assert len(index.all_documents()) == 1

    def test_empty_corpus_handled(self):
        index = DocumentIndex([])
        results = index.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestDocumentIndexSearch:
    def test_search_returns_results(self, sample_index):
        results = sample_index.search("housing benefit rent")
        assert len(results) > 0

    def test_search_result_type(self, sample_index):
        results = sample_index.search("housing benefit")
        assert isinstance(results[0], SearchResult)

    def test_relevant_doc_ranked_first(self, sample_index):
        results = sample_index.search("housing benefit rent low income")
        assert results[0].document_id == "DOC-001"

    def test_business_query_matches_business_doc(self, sample_index):
        results = sample_index.search("register business HMRC tax")
        assert any(r.document_id == "DOC-002" for r in results)

    def test_search_returns_passage_not_empty(self, sample_index):
        results = sample_index.search("housing benefit")
        assert all(r.passage for r in results)

    def test_search_respects_top_n(self, sample_index):
        results = sample_index.search("benefit", top_n=1)
        assert len(results) <= 1

    def test_unrelated_query_returns_empty(self, sample_index):
        results = sample_index.search("quantum physics astronomy")
        assert len(results) == 0

    def test_search_result_has_section_heading(self, sample_index):
        results = sample_index.search("savings sixteen thousand")
        assert results[0].section_heading != ""

    def test_search_result_score_between_0_and_1(self, sample_index):
        results = sample_index.search("housing benefit rent")
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_search_result_includes_quality_flags(self, sample_index):
        results = sample_index.search("housing benefit rent")
        assert hasattr(results[0], "quality_flags")


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class TestDocumentIndexFilters:
    def test_status_filter_current_only(self, sample_index):
        results = sample_index.search("council tax benefit", status_filter="current")
        for r in results:
            assert r.status == "current"

    def test_status_filter_excludes_superseded(self, sample_index):
        results = sample_index.search("council tax", status_filter="current")
        assert not any(r.document_id == "DOC-003" for r in results)

    def test_topic_filter_narrows_results(self, sample_index):
        results = sample_index.search("benefit", topic_filter="housing-benefit")
        assert all("housing-benefit" in r.document_id or r.document_id == "DOC-001"
                   for r in results)

    def test_no_filter_returns_all_relevant(self, sample_index):
        results = sample_index.search("tax benefit register")
        assert len(results) >= 2
