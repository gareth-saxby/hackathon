# Challenge 2: Unlocking the Dark Data — Our Response

Government produces an enormous amount of guidance, policy, and procedural documentation. Most of it is published. Very little of it is genuinely findable when someone needs it.

**Our prototype directly addresses this** — a working Streamlit application that extracts, indexes, and searches government policy documents, returning the exact passage that answers a query rather than pointing to a document.

---

## The problem we solved

The brief describes an adviser who puts a caller on hold, finds three documents with similar names and different dates, and gives an answer based on whichever version they found fastest. **Our app eliminates that scenario** for the structured corpus:

- A free-text query returns the **exact passage**, not a document link
- Every result shows **which version is current**, with explicit warnings if a document is stale, superseded, or contradicted by another
- Results are ranked by relevance score — the most relevant passage surfaces first regardless of which document it came from
- **Live GOV.UK content** is blended into results, so the adviser sees both the local corpus and the canonical published guidance in one ranked list

---

## Coverage against the brief

| Brief requirement | Status | Detail |
|---|---|---|
| Extract structured text from documents | ✅ Complete | HTML, Markdown, TXT parsers — all 20 structured docs |
| Define a schema for extracted content | ✅ Complete | `GovernmentDocument` with sections, tables, metadata, quality flags |
| Build a query / search interface | ✅ Complete | TF-IDF passage search, topic & status filters, relevance scoring |
| Surface the right passage, not just the document | ✅ Complete | Section-level retrieval, matched terms highlighted |
| Identify stale and superseded content | ✅ Complete | STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION flags with dashboard |
| Use the GOV.UK Content API | ✅ Complete | Live search + content fetch, department-inferred filtering, blended ranking |
| Structured files (20 docs, HTML/MD/TXT) | ✅ Complete | All 20 indexed, tested, extracted to JSON cache |
| Unstructured files (23 docs, PDF/DOCX/XLSX) | ⬜ Not started | Parsers for binary formats not yet implemented |
| data.gov.uk integration | ⬜ Not started | Identified as stretch goal |
| Target user — frontline adviser | ✅ Primary focus | Citation block, quality warnings, status badges all adviser-oriented |
| Target user — citizen | ⚡ Partial | Interface works; not tuned for plain-English citizen queries |
| Target user — developer | ⚡ Partial | JSON schema and extraction pipeline exist; no API endpoint yet |
| Target user — policy owner | ⚡ Partial | Data Quality dashboard shows flag counts; no publishing analytics |

---

## What the brief defines as a good outcome

> *"A set of documents whose content has been extracted and structured, a way to query or search that content, and a clear explanation of who benefits and how."*

**We have all three.** The remaining gap is the unstructured corpus (23 binary files) — the parsers for PDF, DOCX, and XLSX are the one outstanding piece before the full 43-document corpus can be indexed.

---

## How to run the app

```bash
cd hackathon/challenge-2
streamlit run app.py
```

Opens at `http://localhost:8501`

---

## Good demo queries

```
housing benefit savings below £16000 rent low income
statutory sick pay employer eligibility
flexible working request employer rights
self employed register tax income
```

Enable the **🌐 Live GOV.UK** toggle to blend live GOV.UK passages into the same ranked results list.

---

*Branch: `feature/api_retrieval` · Date: 16 April 2026*
