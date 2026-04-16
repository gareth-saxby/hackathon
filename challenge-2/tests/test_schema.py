"""
test_schema.py — Tests for GovernmentDocument dataclass and QualityFlag enum.
"""
from __future__ import annotations

import pytest
from src.schema import GovernmentDocument, QualityFlag, Section, Table


# ---------------------------------------------------------------------------
# QualityFlag
# ---------------------------------------------------------------------------

class TestQualityFlag:
    def test_all_expected_values_exist(self):
        values = {f.value for f in QualityFlag}
        assert values == {"STALE", "SUPERSEDED", "MISSING_METADATA", "CONTRADICTION"}

    def test_is_string_subclass(self):
        assert isinstance(QualityFlag.STALE, str)
        assert QualityFlag.STALE == "STALE"


# ---------------------------------------------------------------------------
# GovernmentDocument.to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestGovernmentDocumentRoundTrip:
    def _make_doc(self) -> GovernmentDocument:
        return GovernmentDocument(
            document_id="DOC-T-001",
            title="Test Doc",
            department="Test Dept",
            document_type="guidance",
            status="current",
            publication_date="2025-01-01",
            last_updated="2025-06-01",
            audience="Citizens",
            topics=["housing", "benefits"],
            version="1.0",
            supersedes="DOC-T-000",
            related_documents=["DOC-T-002"],
            sections=[Section(heading="Overview", level=1, body="Overview text.")],
            tables=[
                Table(
                    caption="Limits",
                    headers=["Item", "Value"],
                    rows=[["Capital", "£16,000"]],
                )
            ],
            keywords=["housing"],
            quality_flags=[QualityFlag.STALE],
            source_file="/docs/DOC-T-001.html",
            source_format="html",
        )

    def test_to_dict_keys(self):
        d = self._make_doc().to_dict()
        expected_keys = {
            "document_id", "title", "department", "document_type", "status",
            "publication_date", "last_updated", "audience", "topics", "version",
            "supersedes", "related_documents", "sections", "tables", "keywords",
            "quality_flags", "source_file", "source_format",
        }
        assert expected_keys == set(d.keys())

    def test_quality_flags_serialised_as_strings(self):
        d = self._make_doc().to_dict()
        assert d["quality_flags"] == ["STALE"]

    def test_sections_serialised(self):
        d = self._make_doc().to_dict()
        assert d["sections"] == [{"heading": "Overview", "level": 1, "body": "Overview text."}]

    def test_tables_serialised(self):
        d = self._make_doc().to_dict()
        assert d["tables"] == [
            {"caption": "Limits", "headers": ["Item", "Value"], "rows": [["Capital", "£16,000"]]}
        ]

    def test_from_dict_restores_document(self):
        original = self._make_doc()
        restored = GovernmentDocument.from_dict(original.to_dict())

        assert restored.document_id == original.document_id
        assert restored.title == original.title
        assert restored.topics == original.topics
        assert restored.quality_flags == original.quality_flags
        assert len(restored.sections) == len(original.sections)
        assert restored.sections[0].heading == "Overview"
        assert restored.tables[0].headers == ["Item", "Value"]

    def test_from_dict_tolerates_unknown_flag(self):
        data = self._make_doc().to_dict()
        data["quality_flags"] = ["STALE", "UNKNOWN_FLAG"]
        doc = GovernmentDocument.from_dict(data)
        assert doc.quality_flags == [QualityFlag.STALE]

    def test_from_dict_missing_optional_fields(self):
        doc = GovernmentDocument.from_dict(
            {"document_id": "X", "title": "Minimal"}
        )
        assert doc.document_id == "X"
        assert doc.department is None
        assert doc.topics == []
        assert doc.quality_flags == []


# ---------------------------------------------------------------------------
# Empty document defaults
# ---------------------------------------------------------------------------

class TestGovernmentDocumentDefaults:
    def test_lists_default_to_empty(self):
        doc = GovernmentDocument(document_id="X", title="T")
        assert doc.topics == []
        assert doc.sections == []
        assert doc.quality_flags == []
        assert doc.related_documents == []

    def test_optional_fields_default_to_none(self):
        doc = GovernmentDocument(document_id="X", title="T")
        assert doc.department is None
        assert doc.status is None
        assert doc.publication_date is None
