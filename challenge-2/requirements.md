# Challenge 2: Unlocking the Dark Data — Requirements

**Hackathon:** DSIT AI Engineering Lab, London 2026  
**Branch:** feat/Prince  
**Date:** 16 April 2026

---

## 1. Problem Statement

Government guidance documents exist but are not findable or queryable. Frontline advisers searching for policy answers under time pressure must trawl shared drives, guess which document is current, and risk giving citizens wrong information based on an outdated version.

---

## 2. Target User

**Frontline adviser / caseworker**

- Needs the right policy answer quickly while on a call or handling a case
- Works across multiple policy domains (housing benefit, council tax, small business)
- Cannot afford to read entire documents — needs the relevant passage surfaced directly
- Must know whether the document they are reading is current or superseded

---

## 3. Data Source

**Structured files only** — `challenge-2/structured_files/`

- 20 text-based government documents in HTML, Markdown, and plain text formats
- Two policy domains: housing & benefits (DOC-HB-*), small business & employment (DOC-SB-*)
- Documents contain deliberate data quality issues: stale content, internal contradictions, hidden supersession relationships, metadata gaps

---

## 4. Functional Requirements

### 4.1 Document Extraction
- FR-01: Parse all HTML files and extract title, metadata, sections (heading + body), and tables
- FR-02: Parse all Markdown files including YAML front matter for metadata
- FR-03: Parse all plain text files using heading pattern detection
- FR-04: Output each document as a structured JSON object conforming to a defined schema
- FR-05: Detect and flag data quality issues per document (see section 6)

### 4.2 Search
- FR-06: Build a TF-IDF search index over all extracted document sections
- FR-07: Accept a free-text query and return the top-N most relevant passages
- FR-08: Each result must show: document title, section heading, matched passage snippet, source document ID, publication date, and current status
- FR-09: Support filtering results by topic and by document status (current / stale / superseded)

### 4.3 Data Quality
- FR-10: Flag documents where `status` is marked `current` but `last_updated` is more than 12 months ago
- FR-11: Flag documents that are superseded by another document in the corpus
- FR-12: Flag documents with missing required metadata fields (title, department, publication date)
- FR-13: Flag cross-document contradictions where the same policy value differs between documents

### 4.4 User Interface
- FR-14: Streamlit web app with the following tabs:
  - **Search** — free-text query box, results with highlighted passage, source and date
  - **Browse** — list all documents with status badges and metadata summary
  - **Data Quality** — dashboard showing all flagged issues across the corpus
- FR-15: Data quality warnings must be visible inline on search results (e.g. ⚠️ This document may be superseded)
- FR-16: Results must show the matched passage, not just the document title

---

## 5. Non-Functional Requirements

- NFR-01: Fully local — no LLM API key required, no external API calls at runtime
- NFR-02: All code under `AI-Hackathon-DSIT-2026/hackathon/challenge-2/`
- NFR-03: Python 3.10+ compatible
- NFR-04: Must run with a single command: `streamlit run app.py`
- NFR-05: No access to any other folders in the workspace outside `AI-Hackathon-DSIT-2026/`

---

## 6. Data Quality Flag Definitions

| Flag | Condition |
|---|---|
| `STALE` | `status = current` but `last_updated` > 12 months ago |
| `SUPERSEDED` | Another document in corpus has `supersedes` pointing to this doc ID |
| `MISSING_METADATA` | One or more of: title, department, publication_date is absent |
| `CONTRADICTION` | Same named policy value (e.g. capital threshold) differs across docs |

---

## 7. Document Schema (JSON)

```json
{
  "document_id": "string",
  "title": "string",
  "department": "string | null",
  "document_type": "string | null",
  "status": "current | draft | superseded | null",
  "publication_date": "YYYY-MM-DD | null",
  "last_updated": "YYYY-MM-DD | null",
  "audience": "string | null",
  "topics": ["string"],
  "version": "string | null",
  "supersedes": "string | null",
  "related_documents": ["string"],
  "sections": [
    { "heading": "string", "level": 1, "body": "string" }
  ],
  "tables": [
    { "caption": "string | null", "headers": ["string"], "rows": [["string"]] }
  ],
  "keywords": ["string"],
  "quality_flags": ["STALE", "SUPERSEDED", "MISSING_METADATA", "CONTRADICTION"],
  "source_file": "string",
  "source_format": "html | markdown | txt"
}
```

---

## 8. Tech Stack

| Component | Library |
|---|---|
| HTML parsing | `beautifulsoup4` |
| Markdown parsing | `markdown-it-py` |
| YAML front matter | `python-frontmatter` |
| Search / TF-IDF | `scikit-learn` |
| Web UI | `streamlit` |
| Data handling | `json`, `pathlib` (stdlib) |

---

## 9. File Structure

```
hackathon/challenge-2/
├── requirements.md          # This file
├── requirements.txt         # Python dependencies
├── app.py                   # Streamlit entry point
├── src/
│   ├── __init__.py
│   ├── schema.py            # GovernmentDocument dataclass
│   ├── extractor.py         # HTML / Markdown / TXT parsers
│   ├── indexer.py           # TF-IDF index builder and search
│   └── qa.py                # Passage retrieval and Q&A logic
└── data/
    └── extracted/           # Generated JSON output (gitignored)
```

---

## 10. Build Order

1. `schema.py` — document data model and quality flag types  
2. `extractor.py` — parse HTML, Markdown, TXT → GovernmentDocument  
3. `indexer.py` — build TF-IDF index, run search queries  
4. `qa.py` — retrieve best matching passage for a question  
5. `app.py` — Streamlit UI: Search, Browse, Data Quality tabs  
6. `requirements.txt` — all Python dependencies  
