"""
Tests for src/extractor.py — HTML, Markdown, plain text parsers.
"""
import textwrap
import pytest

from src.extractor import load_all_documents
from src.schema import GovernmentDocument


# ---------------------------------------------------------------------------
# Helpers — inline document fixtures
# ---------------------------------------------------------------------------

HTML_DOC = textwrap.dedent("""\
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="document-id" content="DOC-HB-001">
        <meta name="author" content="Department A">
        <meta name="document-type" content="guidance">
        <meta name="status" content="current">
        <meta name="publication-date" content="2025-06-15">
        <meta name="last-updated" content="2025-11-20">
        <meta name="audience" content="Citizens">
        <meta name="topics" content="housing-benefit, benefits">
        <title>Housing Benefit Eligibility</title>
    </head>
    <body>
        <h1>Housing Benefit Eligibility</h1>
        <h2>Overview</h2>
        <p>Housing Benefit helps pay your rent.</p>
        <h2>Who can claim</h2>
        <p>You must be on a low income.</p>
        <table>
            <tr><th>Criteria</th><th>Threshold</th></tr>
            <tr><td>Savings</td><td>£16,000</td></tr>
        </table>
    </body>
    </html>
""")

MARKDOWN_DOC = textwrap.dedent("""\
    ---
    document_id: DOC-HB-002
    title: "Discretionary Housing Payments"
    department: "[DEPT-A]"
    type: procedural-manual
    status: current
    publication_date: 2025-03-01
    last_updated: 2025-09-15
    audience: Local authority officers
    version: "2.1"
    supersedes: "DOC-HB-002 v1.4"
    topics:
      - housing-benefit
      - discretionary-housing-payments
    related_documents:
      - DOC-HB-001
    ---

    # Discretionary Housing Payments

    ## Purpose and scope

    This manual covers the procedural framework for DHPs.

    ## Eligibility assessment

    Officers must confirm Housing Benefit entitlement first.

    | Criterion | Detail |
    |---|---|
    | Gateway | HB or UC housing element |
""")

TXT_DOC = textwrap.dedent("""\
    Document ID: DOC-HB-003
    Title: Council Tax Reduction Schemes
    Department: Government Department A
    Status: Current
    Published: March 2024
    Audience: Local authority officers

    1. Introduction

    This document covers the CTR regulatory framework.

    2. Scope of local authority discretion

    Billing authorities may design their own schemes.
""")


# ---------------------------------------------------------------------------
# HTML extractor
# ---------------------------------------------------------------------------

class TestHTMLExtractor:
    def _parse(self):
        from src.extractor import _extract_html
        return _extract_html(HTML_DOC, "DOC-HB-001.html")

    def test_document_id(self):
        assert self._parse().document_id == "DOC-HB-001"

    def test_title(self):
        assert "Housing Benefit" in self._parse().title

    def test_department(self):
        assert self._parse().department == "Department A"

    def test_status(self):
        assert self._parse().status == "current"

    def test_publication_date(self):
        assert self._parse().publication_date == "2025-06-15"

    def test_last_updated(self):
        assert self._parse().last_updated == "2025-11-20"

    def test_topics_parsed(self):
        doc = self._parse()
        assert "housing-benefit" in doc.topics
        assert "benefits" in doc.topics

    def test_sections_extracted(self):
        doc = self._parse()
        headings = [s.heading for s in doc.sections]
        assert "Overview" in headings
        assert "Who can claim" in headings

    def test_section_body_populated(self):
        doc = self._parse()
        overview = next(s for s in doc.sections if s.heading == "Overview")
        assert "rent" in overview.body.lower()

    def test_table_extracted(self):
        doc = self._parse()
        assert len(doc.tables) == 1
        assert "Savings" in doc.tables[0].rows[0]

    def test_source_format(self):
        assert self._parse().source_format == "html"

    def test_keywords_populated(self):
        assert len(self._parse().keywords) > 0


# ---------------------------------------------------------------------------
# Markdown extractor
# ---------------------------------------------------------------------------

class TestMarkdownExtractor:
    def _parse(self):
        from src.extractor import _extract_markdown
        return _extract_markdown(MARKDOWN_DOC, "DOC-HB-002.md")

    def test_document_id(self):
        assert self._parse().document_id == "DOC-HB-002"

    def test_title(self):
        assert "Discretionary" in self._parse().title

    def test_version(self):
        assert self._parse().version == "2.1"

    def test_supersedes(self):
        assert "DOC-HB-002" in self._parse().supersedes

    def test_related_documents(self):
        assert "DOC-HB-001" in self._parse().related_documents

    def test_topics_are_strings(self):
        doc = self._parse()
        for t in doc.topics:
            assert isinstance(t, str), f"Expected str, got {type(t)}: {t}"

    def test_publication_date_is_string(self):
        doc = self._parse()
        assert isinstance(doc.publication_date, str)
        assert doc.publication_date == "2025-03-01"

    def test_last_updated_is_string(self):
        doc = self._parse()
        assert isinstance(doc.last_updated, str)

    def test_sections_extracted(self):
        doc = self._parse()
        headings = [s.heading for s in doc.sections]
        assert "Purpose and scope" in headings

    def test_source_format(self):
        assert self._parse().source_format == "markdown"


# ---------------------------------------------------------------------------
# Plain text extractor
# ---------------------------------------------------------------------------

class TestTxtExtractor:
    def _parse(self):
        from src.extractor import _extract_txt
        return _extract_txt(TXT_DOC, "DOC-HB-003.txt")

    def test_document_id(self):
        assert self._parse().document_id == "DOC-HB-003"

    def test_title(self):
        assert "Council Tax" in self._parse().title

    def test_department(self):
        assert self._parse().department is not None

    def test_status(self):
        doc = self._parse()
        assert doc.status is not None

    def test_sections_extracted(self):
        doc = self._parse()
        assert len(doc.sections) >= 1

    def test_source_format(self):
        assert self._parse().source_format == "txt"

    def test_raw_text_populated(self):
        doc = self._parse()
        assert len(doc.raw_text) > 0


# ---------------------------------------------------------------------------
# load_all_documents — integration
# ---------------------------------------------------------------------------

class TestLoadAllDocuments:
    def test_loads_structured_files(self):
        from pathlib import Path
        data_dir = (
            Path(__file__).parent.parent.parent.parent
            / "ai-engineering-lab-hackathon-london-2026/challenge-2/structured_files"
        )
        if not data_dir.exists():
            pytest.skip("Structured files directory not found")
        docs = load_all_documents(str(data_dir))
        assert len(docs) > 0

    def test_all_docs_have_title(self):
        from pathlib import Path
        data_dir = (
            Path(__file__).parent.parent.parent.parent
            / "ai-engineering-lab-hackathon-london-2026/challenge-2/structured_files"
        )
        if not data_dir.exists():
            pytest.skip("Structured files directory not found")
        docs = load_all_documents(str(data_dir))
        for doc in docs:
            assert doc.title, f"{doc.source_file} has no title"

    def test_all_docs_are_government_documents(self):
        from pathlib import Path
        data_dir = (
            Path(__file__).parent.parent.parent.parent
            / "ai-engineering-lab-hackathon-london-2026/challenge-2/structured_files"
        )
        if not data_dir.exists():
            pytest.skip("Structured files directory not found")
        docs = load_all_documents(str(data_dir))
        for doc in docs:
            assert isinstance(doc, GovernmentDocument)
