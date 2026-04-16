# Future Plans — Government Document Search Tool

This document captures what comes next beyond the hackathon prototype: what to build, in what order, and why. Items are grouped by phase and priority. The goal is a production-ready tool that a real government caseworker could use daily.

---

## Priority order

Items at the top deliver the most value per unit of effort.

---

## Phase A — Immediate next step: GOV.UK Content API

### A1. Verify and complete GOV.UK Content API integration *(in progress)*

The API integration is already underway in the current codebase. The immediate goal is to verify it is working correctly end-to-end — that live GOV.UK content is being fetched, parsed, and indexed into the same schema as local documents, and that search results from the API surface correctly alongside local results.

The API is free and requires no authentication:

```
GET https://www.gov.uk/api/content/[any-govuk-path]
```

**Verify:**
- A GOV.UK path entered by the user correctly fetches and parses the response
- The resulting document conforms to the `GovernmentDocument` schema
- It appears in search results alongside local documents
- Quality flags (stale, missing metadata) are applied consistently to API-sourced content
- Error handling is in place for invalid paths or unreachable endpoints

**Why this matters:** This is the step that takes the tool beyond a fixed document set. A caseworker can pull in any newly published guidance from GOV.UK in real time without waiting for a manual extraction run.

---

## Phase B — Improve the search and reading experience

### B1. Keyword highlighting in full document view

When a user expands to read the full section text, highlight the matched query terms inline. Standard search UX that significantly improves scannability under time pressure.

**Effort:** Low — apply a simple regex highlight to the passage HTML before rendering.

### B2. Document version timeline

For any document flagged as superseded, show a small visual timeline of versions with dates — which document replaced which, and when. Directly addresses the "which version is current?" problem that advisers face on shared drives.

**Effort:** Medium — requires supersession chain traversal in the indexer.

### B3. Search history

Store the last 10 searches in session state so a caseworker can revisit a query from earlier in the same call without retyping. Small but realistic UX improvement for the primary user.

**Effort:** Low.

---

## Phase C — Production frontend (higher priority at production level, higher effort)

Streamlit is the right tool for a hackathon prototype. It is not suitable for a production caseworker interface. The constraints that matter for this user — accessibility, keyboard navigation, responsive layout, screen reader support — require a proper frontend framework.

### Recommended stack

```
Frontend:  Next.js (React)
Backend:   FastAPI (Python)
Styling:   GOV.UK Frontend npm package (govuk-frontend)
```

**Why this split:**
- All existing Python extraction and search code stays entirely unchanged
- FastAPI adds a thin REST layer: `GET /search?q=...`, `GET /document/{id}`
- Next.js handles routing, accessibility, and GOV.UK component library
- The GOV.UK Frontend package provides buttons, inputs, phase banners, tags, and notification banners that match the live GOV.UK design out of the box — no custom CSS required

**What this enables that Streamlit cannot provide:**
- Full WCAG 2.2 AA accessibility compliance
- Keyboard navigation throughout
- GOV.UK-standard focus states (yellow `#ffdd00` ring)
- Mobile-responsive layout
- Proper page titles and skip links for screen readers
- Print-friendly citation view for caseworker records

**Approximate effort:** High — but a developer familiar with Next.js could scaffold the app and wire up the FastAPI search endpoint in roughly half a day. GOV.UK Frontend components are well-documented and copy-paste ready.

---

## Phase D — Extend data sources and intelligence

### D1. Embeddings-based semantic search

Replace or augment TF-IDF with sentence embeddings (e.g. `sentence-transformers`, `all-MiniLM-L6-v2`) for better handling of synonyms, paraphrased queries, and cross-domain conceptual matches.

**When to prioritise:** Only once the document corpus is large enough that keyword search quality becomes a noticeable problem. For 20–50 documents, TF-IDF is accurate enough. For 200+ documents, embeddings become worth the complexity.

**Effort:** High — requires model loading, vector storage, and a similarity search library (e.g. FAISS or ChromaDB).

### D2. Agentic chatbot *(lowest priority)*

An agentic assistant that can take a multi-step query — e.g. *"My client is self-employed with savings of £12,000 — are they eligible for housing benefit, and what should they do next?"* — and reason across multiple documents to produce a structured response with cited sources.

This goes beyond retrieval into reasoning. It requires either a hosted LLM API or a locally run model, and introduces hallucination risk that would need careful mitigation before it could be used in a caseworker context.

**Effort:** High — significant architectural change; treat as a separate product track rather than a feature addition.

---

## Phase E — Policy owner and admin capabilities

The challenge spec identifies a fourth user: the **policy owner** who publishes guidance and currently has no visibility into whether it is being found, used correctly, or becoming outdated.

### E1. Policy owner dashboard

A separate view showing:
- Which documents are most searched
- Which documents are flagged as stale or superseded but still being retrieved
- Metadata completeness across the corpus
- Cross-reference gaps (documents that reference others that no longer exist)

**Effort:** Medium — the quality data is already computed; this is primarily a UI and reporting task.

### E2. Feedback mechanism *(low priority)*

Thumbs up / down on individual search results, stored locally or in a lightweight database. Aggregated feedback surfaces which results caseworkers find helpful or misleading — the first step toward relevance tuning.

**Effort:** Low for prototype, Medium for production (requires persistent storage).

---

## Summary table

| Phase | Item | Effort | Priority |
|-------|------|--------|----------|
| A | Verify GOV.UK Content API end-to-end | Low | **Immediate** |
| B | Keyword highlighting | Low | High |
| B | Document version timeline | Medium | Medium |
| B | Search history | Low | Low |
| C | Replace Streamlit with Next.js + FastAPI | High | **High at production** |
| D | Embeddings-based semantic search | High | Medium |
| D | Agentic chatbot | High | Lowest |
| E | Policy owner dashboard | Medium | Medium |
| E | Feedback mechanism | Low–Medium | Low |
