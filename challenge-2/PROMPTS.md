# Challenge 2 — AI Coding Prompts Log

This document records the sequence of chat prompts used to reach the current state of the Challenge 2 prototype. It is intended as a reference for teammates, a retrospective aid, and a replayable recipe for rebuilding the codebase from scratch.

**Event:** DSIT AI Engineering Lab, London 2026  
**Branch:** `feat/Prince`  
**Date:** 16 April 2026

---

## How to use this document

Each prompt is shown as it was (or should be) sent to the AI coding assistant. They are ordered chronologically. Each section notes what was produced and what files were created or changed.

---

## Phase 0 — Understanding the Problem

### Prompt 0.1 — Explore the citizen experience

```
I am designing a system to make government guidance documents searchable
and usable. Walk me through the experience of a citizen trying to find
out whether they qualify for a specific benefit, starting from GOV.UK.
Where does the experience break down? What do they need that they are
not getting?
```

**Purpose:** Frame the problem and establish user empathy before writing any code.

---

### Prompt 0.2 — Explore the frontline adviser experience

```
A frontline adviser is on a call and needs to find the right policy
guidance quickly. The guidance is spread across Word documents and PDFs
on a shared drive. Walk me through what that looks like. Where does
time get spent? What could go wrong if they use the wrong version?
```

**Purpose:** Establish the primary target user (frontline adviser / caseworker) and the core risk (wrong version of guidance).

---

### Prompt 0.3 — Explore the developer experience

```
A developer is building a service that needs to surface eligibility
criteria from a policy document. The document is a PDF. What are their
options? What are the risks of each approach?
```

**Purpose:** Understand why structured extraction matters for downstream services.

---

## Phase 1 — Schema Design

### Prompt 1.1 — Define the document schema

```
I need a Python dataclass to represent a parsed government document.
It should capture:
- document_id, title, department, document_type
- status (current | draft | superseded)
- publication_date, last_updated (as strings)
- audience, topics (list of strings), version, supersedes
- related_documents (list of strings)
- sections (each with heading, level int, body text)
- tables (each with caption, headers list, rows list of lists)
- keywords (list), quality_flags (list of enum values)
- source_file (str), source_format (str: html | markdown | txt)

Include a QualityFlag enum with values: STALE, SUPERSEDED,
MISSING_METADATA, CONTRADICTION.

Include a to_dict() method that serialises everything to a plain dict.

Put this in src/schema.py.
```

**Produces:** `src/schema.py`

---

## Phase 2 — Extraction Pipeline

### Prompt 2.1 — HTML parser

```
Create src/extractor.py.

Write a parse_html(path: Path) -> GovernmentDocument function that:
- Reads an HTML file
- Extracts metadata from <meta> tags with these name attributes:
  document-id, department, status, publication-date, last-updated,
  audience, topics (comma-separated), document-type, version,
  supersedes, related-documents (comma-separated)
- Extracts the page title from <title>, stripping any " - GOV.UK" suffix
- Extracts sections by walking h1–h6 tags; each section body is the
  text of all sibling elements until the next heading
- Extracts tables: headers from <thead> or first <tr> with <th>,
  rows from <td> cells
- Falls back to full body text as a single section if no headings found
- Sets source_format = "html" and source_file = str(path)
- Imports GovernmentDocument, Section, Table, QualityFlag from .schema
```

**Produces:** `parse_html()` in `src/extractor.py`

---

### Prompt 2.2 — Markdown parser

```
Add a parse_markdown(path: Path) -> GovernmentDocument function to
src/extractor.py.

It should:
- Use python-frontmatter to parse YAML front matter for these fields:
  document_id, title, department, type (→ document_type), status,
  publication_date, last_updated, audience, version, supersedes,
  topics (list or comma-string), related_documents
- Fall back to the filename stem as document_id if not in front matter
- Parse the Markdown body using markdown-it-py
- Extract sections by walking headings (h1–h6 tokens)
- For each heading collect all inline/paragraph content until the next heading
- Extract tables from table tokens: header cells and body rows
- Set source_format = "markdown"
```

**Produces:** `parse_markdown()` in `src/extractor.py`

---

### Prompt 2.3 — Plain text parser

```
Add a parse_txt(path: Path) -> GovernmentDocument function to
src/extractor.py.

Plain text files have no formal metadata tags. The function should:
- Detect heading lines using this heuristic: a line is a heading if
  it is ALL CAPS, or ends with a colon and is fewer than 80 chars,
  or matches a numbered heading pattern like "1." / "1.1"
- Assign heading level 1 to the first detected heading, level 2 to
  subsequent same-pattern headings
- Use the filename stem as document_id
- Set title to the first heading found, or the filename stem
- Collect body text between headings as section body
- Set source_format = "txt"
```

**Produces:** `parse_txt()` in `src/extractor.py`

---

### Prompt 2.4 — Quality flag detection

```
Add these quality-flag helper functions to src/extractor.py:

_flag_stale(doc: GovernmentDocument) -> bool
  Returns True if status == "current" and last_updated (or
  publication_date as fallback) is more than 12 months ago.
  Use date.today() for the comparison.

_flag_missing_metadata(doc: GovernmentDocument) -> bool
  Returns True if any of title, department, publication_date is absent.

Then add apply_corpus_flags(docs: List[GovernmentDocument]) -> None
  This should:
  - Apply STALE and MISSING_METADATA per document
  - Build a set of superseded IDs by collecting doc.supersedes values
    across the corpus, then flag any doc whose document_id is in that set
  - Detect CONTRADICTION: find any two documents that contain the same
    named monetary value (e.g. "£16,000" appearing with a different
    amount in another doc for the same field name). Flag both documents.
```

**Produces:** `_flag_stale()`, `_flag_missing_metadata()`, `apply_corpus_flags()` in `src/extractor.py`

---

### Prompt 2.5 — extract_all, save, and load

```
Add these three functions to src/extractor.py:

extract_all(data_dir: Path) -> List[GovernmentDocument]
  - Glob for *.html, *.md, *.txt files in data_dir
  - Route each file to the correct parser by suffix
  - Call apply_corpus_flags() on the full list before returning

save_extracted(docs: List[GovernmentDocument], out_dir: Path) -> None
  - Create out_dir if it does not exist
  - Write each doc as {document_id}.json using doc.to_dict()

load_extracted(out_dir: Path) -> List[GovernmentDocument]
  - Read all *.json files from out_dir
  - Reconstruct GovernmentDocument objects from the dicts
  - Return the list (no re-flagging needed — flags are persisted)
```

**Produces:** `extract_all()`, `save_extracted()`, `load_extracted()` in `src/extractor.py`

---

## Phase 3 — Search Index

### Prompt 3.1 — TF-IDF document index

```
Create src/indexer.py.

Define a SearchResult dataclass with fields:
  document_id, title, section_heading, passage, publication_date,
  status, quality_flags (List[str]), score (float), topics (List[str])

Add properties:
  is_stale -> bool   (checks "STALE" in quality_flags)
  is_superseded -> bool
  flag_summary -> Optional[str]  (human-readable warning string)

Define a DocumentIndex class with:
  build(documents: List[GovernmentDocument]) -> None
    - For each document section, create a text chunk:
        "{section.heading} {section.body}"
    - Fit a TfidfVectorizer over all chunks
      (ngram_range=(1,2), sublinear_tf=True, max_df=0.95)
    - Store the fitted vectoriser and sparse matrix

  search(query, top_n=10, topic_filter=None, status_filter=None)
  -> List[SearchResult]
    - Transform the query with the fitted vectoriser
    - Compute cosine similarity against the matrix
    - Sort by score descending, apply filters, return top_n
    - Each SearchResult passage is the raw section body text

  get_all_topics() -> List[str]
    - Return sorted unique topics across all indexed documents

  documents property -> List[GovernmentDocument]

Also define _effective_status(doc) -> str at module level:
  Returns "superseded" if SUPERSEDED flag, "stale" if STALE flag,
  otherwise doc.status or "unknown".
```

**Produces:** `src/indexer.py`

---

## Phase 4 — QA Layer

### Prompt 4.1 — Passage retrieval

```
Create src/qa.py.

Define an Answer dataclass:
  passage, document_id, title, section_heading,
  publication_date, status, quality_flags, score (float)

Add a confidence property:
  "high" if score >= 0.3, "medium" if >= 0.1, else "low"

Define ask(index: DocumentIndex, question: str) -> Optional[Answer]:
  - Calls index.search(question, top_n=1)
  - Returns None if no results
  - Maps the single SearchResult to an Answer and returns it

No LLM, no external API calls.
```

**Produces:** `src/qa.py`

---

## Phase 5 — Streamlit UI

### Prompt 5.1 — App scaffold and data loading

```
Create app.py in the challenge-2 directory.

Set up a Streamlit page (page_title="Dark Data Explorer", layout="wide").

Resolve paths:
  APP_DIR  = Path(__file__).resolve().parent
  DATA_DIR = APP_DIR.parent / "challenge-info" / "data" / "structured_files"
  EXTRACTED_DIR = APP_DIR / "data" / "extracted"
  Allow DATA_DIR to be overridden by a DATA_DIR environment variable.

Add a cached load_index() function decorated with @st.cache_resource:
  - If EXTRACTED_DIR exists and contains *.json files, call load_extracted()
  - Otherwise call extract_all(DATA_DIR), then save_extracted()
  - Build and return a DocumentIndex

Add a sidebar with:
  - Title "🔍 Dark Data Explorer"
  - Caption showing document count
  - Radio nav: Search | Browse | Data Quality
  - A "♻️ Re-extract documents" button that clears the cache and reruns
```

**Produces:** `app.py` (scaffold)

---

### Prompt 5.2 — Search tab

```
Add the Search tab to app.py.

When page == "Search":
  - Show a text input for the query
  - Two select boxes: topic filter (from index.get_all_topics()) and
    status filter (any status | current | stale | superseded)
  - A slider for max results (3–20, default 10)
  - On query entry, call index.search() with the chosen filters
  - For each result render an st.expander showing:
    - Any quality flag warnings as st.warning() calls with emoji badges
      STALE=🟡, SUPERSEDED=🔴, MISSING_METADATA=🟠, CONTRADICTION=🟣
    - The matched passage with query terms bolded
    - Four st.metric columns: Document ID, Status, Published, Relevance %
    - Topic tags as a caption
  - Status icon next to the expander title: 🟢 current, 🟡 stale, 🔴 superseded
```

**Produces:** Search tab in `app.py`

---

### Prompt 5.3 — Browse tab

```
Add the Browse tab to app.py.

When page == "Browse":
  - Show summary metrics: total documents, flagged count, stale count,
    superseded count
  - Render a st.dataframe with columns:
    ID, Title, Status, Department, Published, Topics, Flags
  - Allow the user to click a row and see the full document detail:
    all sections, tables, and metadata in an expander
```

**Produces:** Browse tab in `app.py`

---

### Prompt 5.4 — Data Quality tab

```
Add the Data Quality tab to app.py.

When page == "Data Quality":
  - Group all flagged documents by flag type
  - For each flag type show a subheader and a table of affected documents
    (ID, Title, Department, Published, Status)
  - Add a plain-English explanation of each flag type below the table
  - Show a "documents with no flags" count as a positive summary metric
```

**Produces:** Data Quality tab in `app.py`

---

## Phase 6 — Tests

### Prompt 6.1 — Schema unit tests

```
Create tests/test_schema.py.

Test GovernmentDocument:
  - Can be instantiated with only document_id and title
  - to_dict() returns a dict with all expected keys
  - quality_flags defaults to an empty list
  - sections defaults to an empty list
  - topics defaults to an empty list

Test QualityFlag enum:
  - Values are "STALE", "SUPERSEDED", "MISSING_METADATA", "CONTRADICTION"
```

**Produces:** `tests/test_schema.py`

---

### Prompt 6.2 — Extractor unit tests

```
Create tests/conftest.py with shared fixtures:
  - html_file(tmp_path) — writes a minimal valid HTML file using
    SAMPLE_HTML (inline constant) and returns the Path
  - md_file(tmp_path) — writes a minimal valid Markdown file with
    YAML front matter and returns the Path
  - txt_file(tmp_path) — writes a minimal plain text file and returns the Path

The HTML sample must include:
  - All required meta tags (document-id, department, status,
    publication-date, last-updated, topics)
  - Two h2 sections with body text
  - One table with headers and two data rows

Create tests/test_extractor.py testing:
  - parse_html: document_id, title (GOV.UK suffix stripped), department,
    status, topics split, sections extracted, table extracted,
    source_format == "html"
  - parse_markdown: document_id, title, front matter fields, sections,
    source_format == "markdown"
  - parse_txt: heading detection, section count, source_format == "txt"
  - _flag_stale: returns True for stale doc, False for recent doc
  - _flag_missing_metadata: returns True when fields missing
  - apply_corpus_flags: SUPERSEDED flag propagated, STALE applied
```

**Produces:** `tests/conftest.py`, `tests/test_extractor.py`

---

### Prompt 6.3 — Indexer and QA unit tests

```
Create tests/test_indexer_qa.py.

Use two or three minimal GovernmentDocument fixtures (inline, no files).

Test DocumentIndex:
  - build() with empty list does not raise
  - build() with one doc creates a searchable index
  - search() returns SearchResult objects
  - search() top_n is respected
  - search() with topic_filter excludes non-matching docs
  - search() with status_filter "current" excludes stale/superseded
  - get_all_topics() returns sorted unique topics
  - documents property returns the list passed to build()

Test ask():
  - Returns None for empty index
  - Returns an Answer with passage, document_id, title, score
  - confidence is "high" / "medium" / "low" based on score thresholds
```

**Produces:** `tests/test_indexer_qa.py`

---

### Prompt 6.4 — Integration tests

```
Create tests/test_integration.py marked with pytest.mark.integration.

DATA_DIR = Path(__file__).resolve().parents[2]
           / "challenge-info" / "data" / "structured_files"

Skip all tests if DATA_DIR does not exist.

Test corpus completeness:
  - All 20 documents loaded
  - 10 DOC-HB-* and 10 DOC-SB-* documents present
  - All docs have document_id
  - All docs have at least one section
  - HTML, markdown, and txt formats all parsed

Test quality flags:
  - At least one STALE document in the corpus
  - At least one SUPERSEDED document
  - At least one MISSING_METADATA document

Test search:
  - Query "housing benefit capital limit" returns at least one result
  - Results are ordered by score descending
  - Topic filter "housing" excludes DOC-SB-* documents
  - ask() returns an Answer for a known query

Create pytest.ini marking integration tests:
  [pytest]
  markers =
    integration: tests that require the real data files
```

**Produces:** `tests/test_integration.py`, `pytest.ini`

---

## Phase 7 — Planning and Documentation

### Prompt 7.1 — Generate the hackathon plan

```
Based upon the attribution of information categories between data for
structured and unstructured, and given that we now have a working
prototype that is usable to query against structured, please generate
a plan for this hackathon in markdown format, one that shows how far
progress we are so far and what is left we should do for this hackathon.
Please include an ASCII diagram showing flow also.
```

**Produces:** `HACKATHON-PLAN.md` (initial version with ASCII flow)

---

### Prompt 7.2 — Replace ASCII diagram with Mermaid

```
Can you re-do with a Mermaid diagram instead of an ASCII diagram?
```

**Produces:** Updated `HACKATHON-PLAN.md` with `flowchart TD` Mermaid diagram,
colour-coded green (done) and amber (todo).

---

### Prompt 7.3 — This document

```
Please provide a markdown document of chat prompts for getting to this
state of development for challenge 2 including aforementioned.
```

**Produces:** `PROMPTS.md` (this file)

---

## What comes next

The prompts for Phase 2 (unstructured pipeline) have not been written yet.
When you are ready to continue, start with:

```
Add extract_pdf(path: Path) -> GovernmentDocument to src/extractor.py.
Use pdfplumber to extract text page by page. Detect headings using
ALL-CAPS lines or lines shorter than 80 characters followed by a blank
line. Extract metadata from the first page if it contains lines of the
form "Key: Value". Fall back to filename-based heuristics for
department and publication_date if none is found in the document.
Set source_format = "pdf".
```

Then follow the same pattern for `extract_docx()` (python-docx) and
`extract_xlsx()` (openpyxl), then update `extract_all()` to dispatch
on `.pdf`, `.docx`, and `.xlsx` extensions.

See `HACKATHON-PLAN.md` for the full list of remaining tasks.
