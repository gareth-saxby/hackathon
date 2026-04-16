# Challenge 2 — Unlocking the Dark Data: Hackathon Plan

**Event:** DSIT AI Engineering Lab, London 2026  
**Date:** 16 April 2026  
**Branch:** `feat/Prince`

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INPUT DATA SOURCES                                   │
│                                                                             │
│   ┌──────────────────────────────┐   ┌──────────────────────────────────┐   │
│   │  STRUCTURED FILES  ✅ DONE   │   │  UNSTRUCTURED FILES  ⬜ TODO    │   │
│   │  challenge-info/data/        │   │  challenge-info/data/            │   │
│   │  structured_files/           │   │  unstructured_files/             │   │
│   │                              │   │                                  │   │
│   │  20 documents                │   │  23 documents                    │   │
│   │  .html  .md  .txt            │   │  .pdf  .docx  .xlsx              │   │
│   │  Housing & Benefits (HB)     │   │  HR policies, briefing packs,    │   │
│   │  Small Business & Empl (SB)  │   │  meeting minutes, spreadsheets   │   │
│   └──────────────┬───────────────┘   └────────────────┬─────────────────┘   │
└──────────────────┼──────────────────────────────────── ┼ ───────────────────┘
                   │                                      │
                   ▼                                      ▼
┌──────────────────────────────┐   ┌──────────────────────────────────────────┐
│  src/extractor.py  ✅ DONE  │   │  src/extractor.py (unstructured) ⬜ TODO │
│                              │   │                                          │
│  parse_html()                │   │  extract_pdf()   — pdfplumber            │
│  parse_markdown()            │   │  extract_docx()  — python-docx           │
│  parse_txt()                 │   │  extract_xlsx()  — openpyxl              │
│  quality flag detection      │   │  filename → metadata heuristics          │
└──────────────┬───────────────┘   └────────────────┬─────────────────────────┘
               │                                      │
               └──────────────┬───────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  src/schema.py  ✅ DONE       │
              │                               │
              │  GovernmentDocument           │
              │  ├── document_id              │
              │  ├── title / department       │
              │  ├── status / dates           │
              │  ├── sections[]               │
              │  ├── tables[]                 │
              │  └── quality_flags[]          │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  data/extracted/*.json ✅ DONE│
              │  (JSON cache, 20 docs)        │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  src/indexer.py  ✅ DONE      │
              │                               │
              │  TF-IDF vectorisation         │
              │  cosine similarity search     │
              │  topic / status filtering     │
              │  STALE / SUPERSEDED /         │
              │  CONTRADICTION detection      │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  src/qa.py  ✅ DONE           │
              │                               │
              │  ask(index, question)         │
              │  → best matching passage      │
              │  + confidence (high/med/low)  │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  app.py — Streamlit UI  ✅ DONE (structured)   ⬜ TODO (unstructured)       │
│                                                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────────────┐ │
│  │  🔍 Search  │   │  📄 Browse   │   │  ⚠️  Data Quality Dashboard      │ │
│  │  free-text  │   │  all docs    │   │  STALE / SUPERSEDED /            │ │
│  │  query box  │   │  status tags │   │  MISSING_METADATA / CONTRADICTION│ │
│  └─────────────┘   └──────────────┘   └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Progress Tracker

### ✅ Phase 1 — Structured Pipeline (COMPLETE)

All 16 functional requirements for the structured data source have been met.

| # | Requirement | Component | Status |
|---|---|---|---|
| FR-01 | Parse HTML → title, metadata, sections, tables | `extractor.parse_html()` | ✅ Done |
| FR-02 | Parse Markdown including YAML front matter | `extractor.parse_markdown()` | ✅ Done |
| FR-03 | Parse plain text with heading detection | `extractor.parse_txt()` | ✅ Done |
| FR-04 | Output structured JSON conforming to schema | `schema.GovernmentDocument.to_dict()` | ✅ Done |
| FR-05 | Detect and flag data quality issues per doc | `extractor._flag_*()` | ✅ Done |
| FR-06 | Build TF-IDF search index over sections | `indexer.DocumentIndex.build()` | ✅ Done |
| FR-07 | Accept free-text query, return top-N passages | `indexer.DocumentIndex.search()` | ✅ Done |
| FR-08 | Show title, section, passage, ID, date, status | `app.py` Search tab | ✅ Done |
| FR-09 | Filter by topic and document status | `indexer.search(topic_filter, status_filter)` | ✅ Done |
| FR-10 | Flag STALE (current + last_updated > 12 months) | `extractor._flag_stale()` | ✅ Done |
| FR-11 | Flag SUPERSEDED (another doc's `supersedes` field) | `indexer._build_superseded_set()` | ✅ Done |
| FR-12 | Flag MISSING_METADATA | `extractor._flag_missing_metadata()` | ✅ Done |
| FR-13 | Flag CONTRADICTION (same policy value differs) | `indexer` contradiction detection | ✅ Done |
| FR-14 | Streamlit app with Search / Browse / Data Quality | `app.py` | ✅ Done |
| FR-15 | Quality warnings inline on search results | `app.py` expander badges | ✅ Done |
| FR-16 | Show matched passage, not just title | `app.py` highlighted passage | ✅ Done |

**20 documents indexed** across two policy domains:
- Housing & Benefits: `DOC-HB-001` → `DOC-HB-010` (HTML / Markdown / TXT)
- Small Business & Employment: `DOC-SB-001` → `DOC-SB-010` (HTML / Markdown / TXT)

**Test suite passing:** `test_schema.py`, `test_extractor.py`, `test_indexer_qa.py`, `test_integration.py`

---

### ⬜ Phase 2 — Unstructured Pipeline (REMAINING WORK)

The challenge provides a second corpus of 23 binary-format documents that simulate a real departmental shared drive. These have not yet been ingested.

#### Data categories in the unstructured corpus

| Category | Files | Format |
|---|---|---|
| HR Policy documents | Annual Leave, Flexible Working, Grievance, Recruitment, Performance Mgmt, Whistleblowing, Social Media | `.docx`, `.pdf` |
| IT & Security Policy | Acceptable Use, Information Security (DRAFT), Incident Reporting | `.pdf`, `.docx` |
| Financial / Procurement | Procurement Thresholds, Spending Controls, Overpayment Recovery | `.xlsx`, `.pdf` |
| Ministerial / Governance | Ministers' Questions Briefing Pack, Programme Board Minutes, Equality Impact Assessment | `.pdf`, `.docx` |
| Benefits Guidance | Housing Benefit Eligibility, Council Tax Reduction, Social Fund Budgeting Loans | `.docx`, `.pdf` |
| Compliance / Legal | Welsh Language Standards, Data Protection Guidance, FOI Response Template | `.pdf`, `.docx` |
| Data / Directories | Staff Directory Extract | `.xlsx` |

#### Tasks remaining

**Step 1 — Add binary parsers to `src/extractor.py` (highest priority)**

- `extract_pdf(path)` using `pdfplumber` — extract text page by page, detect headings by font size / capitalisation heuristics
- `extract_docx(path)` using `python-docx` — walk `document.paragraphs` for heading styles, extract `core_properties` for metadata
- `extract_xlsx(path)` using `openpyxl` — treat sheet names as section headings, serialise rows as Table objects
- Filename → metadata heuristic: derive `department`, `document_type`, `status` (look for "DRAFT" in filename), and `publication_date` from filename tokens when document-internal metadata is absent

**Step 2 — Extend `extract_all()` to include unstructured files**

- Update `extract_all(data_dir)` to call the appropriate parser based on file extension (`.pdf`, `.docx`, `.xlsx`)
- Add file extension to `source_format` field in schema
- Update `save_extracted` / `load_extracted` to handle the combined corpus

**Step 3 — Update `app.py` to surface unstructured results**

- Add a data source toggle (structured / unstructured / both) to the sidebar
- Display `source_format` badge on search results so users can see which format a passage came from
- Show DRAFT flag visually (currently only STALE / SUPERSEDED / MISSING_METADATA / CONTRADICTION flags are shown)

**Step 4 — Unstructured-specific quality flags**

- `DRAFT` — filename or document properties contain "DRAFT" or version string like "v0.x"
- `NO_DATE` — publication date could not be extracted from either the document or its filename

**Step 5 — Update requirements.txt**

```
pdfplumber>=0.11
python-docx>=1.1
openpyxl>=3.1
```

**Step 6 — Add tests**

- `test_extractor.py` — add unit tests for each new parser (PDF, DOCX, XLSX)
- `test_integration.py` — extend to load and assert on the combined 43-document corpus

---

### 🔵 Phase 3 — Stretch Goals (if time permits)

**Priority order** — items at the top have the most impact for demo quality or real-world usefulness.

#### 🥇 High priority

| Goal | Description | Effort | Why it matters |
|---|---|---|---|
| **Replace Streamlit with a proper frontend** | Streamlit is fast for prototyping but limited for a realistic caseworker tool. A **React + FastAPI** stack would give full control over layout, accessibility, keyboard navigation, and responsiveness. Alternatively, **Next.js** with a Python API backend hits a good balance of speed and quality. | High | Streamlit feels like a demo. A React UI feels like a product. Critical for judge impression and real adoption. |
| **Export to JSON API** | FastAPI endpoint exposing `GET /search?q=...` and `GET /document/{id}` — makes the extraction layer usable by other services and developers, not just the UI | Medium | Directly addresses the developer/service team user need from the challenge spec |
| **Cross-corpus contradiction detection** | Detect when the same policy value (e.g. housing benefit capital limit, minimum wage rate) appears with different values across structured and unstructured documents | Medium | High demo impact — shows the tool catching a real data quality problem |
| **GOV.UK Content API integration** | Allow a user to enter a GOV.UK path and pull live content into the index alongside local documents | Medium | Demonstrates real-world scalability beyond the 20 starter documents |

#### 🥈 Medium priority

| Goal | Description | Effort | Why it matters |
|---|---|---|---|
| **Passage confidence explanation** | Show the top TF-IDF terms that drove a result's score ("matched on: housing benefit, self-employed, income") | Low | Helps caseworkers trust or distrust a result — transparency in ranking |
| **Search history / recent queries** | Store the last N searches in session state so a caseworker can revisit queries during a call | Low | Small UX improvement, realistic for the primary user persona |
| **Document version timeline** | For any document that has been superseded, show a visual timeline of versions with dates | Medium | Directly addresses the "which version is current?" problem |
| **Keyword highlighting in full document view** | When a user expands to read the full section, highlight the matched terms | Low | Standard search UX, significantly improves readability |

#### 🥉 Lower priority (if significant time remains)

| Goal | Description | Effort | Why it matters |
|---|---|---|---|
| **Embeddings-based semantic search** | Replace or augment TF-IDF with sentence embeddings (e.g. `sentence-transformers`) for better handling of synonyms and paraphrased queries | High | Meaningful quality improvement but requires a model or library; overkill for demo scope |
| **GOV.UK Design System styling** | Apply GOV.UK frontend styles (colour palette, typography, components) to the UI so it looks like a real government service | Medium | Strong visual signal for judges that you understand the context |
| **Admin / policy owner view** | A separate view showing data quality summary across all documents — stale count, contradiction count, metadata gaps — for the policy owner persona | Medium | Addresses the fourth user from the challenge spec who currently has no visibility |
| **Feedback mechanism** | Thumbs up/down on results, stored locally — simulates the feedback loop a real service would need | Low | Shows product thinking beyond the prototype |

---

#### Frontend recommendation

If rebuilding the UI, the recommended stack for this use case is:

```
Frontend:  Next.js (React) — fast to build, good accessibility defaults, easy deployment
Backend:   FastAPI (Python) — keeps all existing extraction/search code, adds a REST layer
Styling:   GOV.UK Frontend (govuk-frontend npm package) — makes it look like a real service
```

This separates concerns cleanly: the Python search logic stays unchanged, the frontend calls the API. A developer on the team could scaffold a Next.js app and connect it to a FastAPI `/search` endpoint in under an hour, leaving the caseworker UI as the focus.

---

## What to do next (priority order)

```
1.  pip install pdfplumber python-docx openpyxl
2.  Add extract_pdf(), extract_docx(), extract_xlsx() to src/extractor.py
3.  Wire them into extract_all() via extension dispatch
4.  Test against one PDF and one DOCX manually
5.  Run streamlit app with combined corpus
6.  Add source_format badge + DRAFT flag to app.py
7.  Write unit tests for new parsers
8.  Update requirements.txt
```

---

## Key decisions made

| Decision | Rationale |
|---|---|
| TF-IDF over BM25 or embeddings | No LLM API required (NFR-01); scikit-learn is already a dependency; fast enough for 20–50 docs |
| JSON extraction cache | Avoids re-parsing on every Streamlit reload; invalidated by the Re-extract button |
| `_effective_status()` in indexer | Dynamically promotes `status=current` docs to `stale` or `superseded` at query time, so source files don't need to be rewritten |
| Structured-first approach | Gets a working, testable prototype fast; unstructured adds complexity without changing the schema |
