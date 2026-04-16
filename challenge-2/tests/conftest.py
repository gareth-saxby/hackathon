"""
Shared pytest fixtures for Challenge 2 test suite.
"""
import sys
from pathlib import Path

import pytest

# Ensure src is importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema import GovernmentDocument, Section, TableData


@pytest.fixture
def minimal_doc():
    """A valid GovernmentDocument with all required fields."""
    return GovernmentDocument(
        document_id="DOC-TEST-001",
        title="Test Policy",
        department="Test Department",
        document_type="guidance",
        status="current",
        publication_date="2025-01-01",
        last_updated="2025-06-01",
        audience="Staff",
        topics=["policy", "test"],
        version="1.0",
        supersedes=None,
        related_documents=[],
        sections=[
            Section(heading="Overview", level=2, body="This is the overview text."),
            Section(heading="Eligibility", level=2, body="You must be employed."),
        ],
        tables=[],
        keywords=["policy", "test", "employed"],
        quality_flags=[],
        raw_text="Test Policy Overview This is the overview text. Eligibility You must be employed.",
        source_file="test-policy.html",
        source_format="html",
    )


@pytest.fixture
def stale_doc():
    """A document marked current but last updated over 12 months ago."""
    return GovernmentDocument(
        document_id="DOC-TEST-002",
        title="Old Policy",
        department="Test Department",
        document_type="guidance",
        status="current",
        publication_date="2022-01-01",
        last_updated="2023-01-01",  # over 12 months ago
        audience="Staff",
        topics=["housing"],
        version=None,
        supersedes=None,
        related_documents=[],
        sections=[Section(heading="Rules", level=2, body="The old rules.")],
        tables=[],
        keywords=["housing"],
        quality_flags=[],
        raw_text="Old Policy Rules The old rules.",
        source_file="old-policy.txt",
        source_format="txt",
    )


@pytest.fixture
def superseding_doc():
    """A document that supersedes DOC-TEST-002."""
    return GovernmentDocument(
        document_id="DOC-TEST-003",
        title="New Policy",
        department="Test Department",
        document_type="guidance",
        status="current",
        publication_date="2025-01-01",
        last_updated="2025-11-01",
        audience="Staff",
        topics=["housing"],
        version="2.0",
        supersedes="DOC-TEST-002",
        related_documents=[],
        sections=[Section(heading="Rules", level=2, body="The new rules.")],
        tables=[],
        keywords=["housing"],
        quality_flags=[],
        raw_text="New Policy Rules The new rules.",
        source_file="new-policy.md",
        source_format="markdown",
    )
