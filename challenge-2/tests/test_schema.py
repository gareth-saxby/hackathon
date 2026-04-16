"""
Tests for src/schema.py
"""
import pytest
from src.schema import (
    GovernmentDocument, Section, TableData,
    STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION,
)


class TestSectionDataclass:
    def test_section_fields(self):
        s = Section(heading="Overview", level=2, body="Some text.")
        assert s.heading == "Overview"
        assert s.level == 2
        assert s.body == "Some text."

    def test_section_level_range(self):
        for level in [1, 2, 3, 4]:
            s = Section(heading="H", level=level, body="")
            assert s.level == level


class TestTableDataDataclass:
    def test_table_with_data(self):
        t = TableData(
            caption="My Table",
            headers=["Name", "Value"],
            rows=[["Threshold", "£16,000"], ["Taper", "65%"]],
        )
        assert t.caption == "My Table"
        assert len(t.headers) == 2
        assert len(t.rows) == 2

    def test_table_empty_rows(self):
        t = TableData(caption=None, headers=["Col"], rows=[])
        assert t.rows == []
        assert t.caption is None


class TestGovernmentDocumentToDict:
    def test_to_dict_has_all_keys(self, minimal_doc):
        d = minimal_doc.to_dict()
        expected_keys = {
            "document_id", "title", "department", "document_type", "status",
            "publication_date", "last_updated", "audience", "topics",
            "version", "supersedes", "related_documents", "sections",
            "tables", "keywords", "quality_flags", "raw_text",
            "source_file", "source_format",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_sections_serialised(self, minimal_doc):
        d = minimal_doc.to_dict()
        assert isinstance(d["sections"], list)
        assert d["sections"][0] == {
            "heading": "Overview", "level": 2, "body": "This is the overview text."
        }

    def test_to_dict_tables_serialised(self, minimal_doc):
        minimal_doc.tables = [
            TableData(caption="Cap", headers=["A", "B"], rows=[["1", "2"]])
        ]
        d = minimal_doc.to_dict()
        assert d["tables"][0]["caption"] == "Cap"
        assert d["tables"][0]["headers"] == ["A", "B"]
        assert d["tables"][0]["rows"] == [["1", "2"]]

    def test_to_dict_values_match_doc(self, minimal_doc):
        d = minimal_doc.to_dict()
        assert d["document_id"] == "DOC-TEST-001"
        assert d["title"] == "Test Policy"
        assert d["status"] == "current"
        assert d["source_format"] == "html"
        assert d["topics"] == ["policy", "test"]

    def test_to_dict_optional_fields_none(self, minimal_doc):
        minimal_doc.supersedes = None
        minimal_doc.version = None
        d = minimal_doc.to_dict()
        assert d["supersedes"] is None
        assert d["version"] is None


class TestQualityFlagConstants:
    def test_flag_values_are_strings(self):
        assert isinstance(STALE, str)
        assert isinstance(SUPERSEDED, str)
        assert isinstance(MISSING_METADATA, str)
        assert isinstance(CONTRADICTION, str)

    def test_flag_values_are_unique(self):
        flags = {STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION}
        assert len(flags) == 4

    def test_quality_flags_field_mutable(self, minimal_doc):
        minimal_doc.quality_flags.append(STALE)
        assert STALE in minimal_doc.quality_flags
