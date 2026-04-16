"""
conftest.py — shared pytest fixtures for challenge-2 tests.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "challenge-info"
    / "data"
    / "structured_files"
)


# ---------------------------------------------------------------------------
# Inline fixture helpers
# ---------------------------------------------------------------------------

SAMPLE_HTML = textwrap.dedent(
    """\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Test Benefit Guide - GOV.UK</title>
      <meta name="document-id" content="DOC-TEST-001">
      <meta name="department" content="Dept of Testing">
      <meta name="status" content="current">
      <meta name="publication-date" content="2025-01-10">
      <meta name="last-updated" content="2025-01-10">
      <meta name="audience" content="Citizens">
      <meta name="topics" content="testing, benefits">
      <meta name="document-type" content="guidance">
    </head>
    <body>
      <h1>Test Benefit Guide</h1>
      <p>Overview paragraph about test benefits.</p>
      <h2>Eligibility</h2>
      <p>You must have a low income. The capital limit is £16,000.</p>
      <table>
        <thead><tr><th>Criterion</th><th>Threshold</th></tr></thead>
        <tbody>
          <tr><td>Capital</td><td>£16,000</td></tr>
          <tr><td>Income</td><td>£500/week</td></tr>
        </tbody>
      </table>
      <h2>How to apply</h2>
      <p>Contact your local council.</p>
    </body>
    </html>
    """
)

SAMPLE_MARKDOWN = textwrap.dedent(
    """\
    ---
    document_id: DOC-TEST-002
    title: "Test Employment Guide"
    department: Dept of Testing
    type: guidance
    status: current
    publication_date: 2024-06-01
    last_updated: 2024-06-01
    audience: Employers
    version: "1.0"
    topics:
      - employment
      - testing
    supersedes: null
    related_documents:
      - DOC-TEST-001
    ---

    # Test Employment Guide

    ## Overview

    This guide explains test employment rules.

    ## Eligibility

    Workers must meet the test criteria. Statutory sick pay is £109.40 per week.
    """
)

SAMPLE_TXT = textwrap.dedent(
    """\
    TEST HOUSING REGULATIONS

    Document ID: DOC-TEST-003
    Published: March 2023
    Department: Dept of Testing
    Status: Current
    Audience: Local authorities

    1. Introduction

    This regulation covers test housing procedures.

    1.1 Scope

    Applies to all local authorities in England.

    2. Capital Limits

    The capital threshold for this scheme is £6,000, not £16,000.
    """
)

STALE_HTML = textwrap.dedent(
    """\
    <!DOCTYPE html>
    <html><head>
      <title>Old Policy - GOV.UK</title>
      <meta name="document-id" content="DOC-OLD-001">
      <meta name="department" content="Dept of Testing">
      <meta name="status" content="current">
      <meta name="publication-date" content="2020-01-01">
      <meta name="last-updated" content="2020-06-01">
    </head>
    <body>
      <h1>Old Policy</h1>
      <p>This policy has not been updated in years.</p>
    </body></html>
    """
)

NO_META_HTML = textwrap.dedent(
    """\
    <!DOCTYPE html>
    <html><head><title>Nameless Doc</title></head>
    <body><h1>No Metadata</h1><p>Body text only.</p></body>
    </html>
    """
)


@pytest.fixture()
def html_file(tmp_path) -> Path:
    p = tmp_path / "DOC-TEST-001.html"
    p.write_text(SAMPLE_HTML, encoding="utf-8")
    return p


@pytest.fixture()
def md_file(tmp_path) -> Path:
    p = tmp_path / "DOC-TEST-002.md"
    p.write_text(SAMPLE_MARKDOWN, encoding="utf-8")
    return p


@pytest.fixture()
def txt_file(tmp_path) -> Path:
    p = tmp_path / "DOC-TEST-003.txt"
    p.write_text(SAMPLE_TXT, encoding="utf-8")
    return p


@pytest.fixture()
def stale_html_file(tmp_path) -> Path:
    p = tmp_path / "DOC-OLD-001.html"
    p.write_text(STALE_HTML, encoding="utf-8")
    return p


@pytest.fixture()
def no_meta_html_file(tmp_path) -> Path:
    p = tmp_path / "DOC-NOMETA-001.html"
    p.write_text(NO_META_HTML, encoding="utf-8")
    return p


@pytest.fixture()
def real_data_dir() -> Path:
    return DATA_DIR
