# Productionisation Roadmap — GovDoc Search

## Stage 1 — Make it deployable (Days 1-3)

### Containerise with Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Environment config

Currently `DATA_DIR` is hardcoded as a relative path. Replace with an env var:

```python
DATA_DIR = Path(os.environ.get("GOVDOC_DATA_DIR", "...default..."))
```

### Azure deployment options

| Option | When to use |
|---|---|
| Azure Container Apps | Best for this — scales to zero, no infra to manage |
| Azure App Service | If you need always-on, simpler setup |
| AKS | Only if you expect very high concurrent users |

---

## Stage 2 — Replace TF-IDF with a real search backend (Week 1-2)

TF-IDF is the biggest production risk. It:

- Rebuilds entirely on every app restart (slow at scale)
- Can't handle typos — `"housng benefit"` returns nothing
- Has no semantic understanding — `"can I claim?"` doesn't match `"eligibility criteria"`

### Replace with Azure AI Search

- Documents indexed once, persisted in Azure
- Hybrid search (keyword + semantic vector) out of the box
- Handles typos, synonyms, and acronyms natively
- `detect_quality_flags()` and `quality_summary()` stay unchanged — they operate on `GovernmentDocument` objects regardless of where search comes from

```
extractor.py → [unchanged]
indexer.py   → replace DocumentIndex with AzureSearchIndex (same interface)
qa.py        → [unchanged]
app.py       → [unchanged — calls index.search() same as before]
```

---

## Stage 3 — Data pipeline (Week 2-3)

Currently documents are static files on disk. In production:

### Automated ingestion

```
gov.uk Content API → fetcher.py → extractor.py → Azure AI Search index
```

Run on a schedule (Azure Function, daily/weekly) so the corpus stays current automatically. When a document is re-ingested, the STALE flag clears automatically.

### Versioned document store

- Store extracted `GovernmentDocument` JSON in Azure Blob Storage
- Keep prior versions — caseworkers need to know what the guidance said *at decision time*, not just today

---

## Stage 4 — Auth & audit (Week 3-4)

Caseworkers need this for legal reasons:

| Requirement | Solution |
|---|---|
| Who accessed what | Azure App Service + Entra ID (formerly AAD) — single sign-on |
| What was cited in a decision | Extend citation block to write to Azure Table Storage on copy |
| GDPR / data residency | Deploy to UK South region, no PII stored in search index |
| Rate limiting | API Management in front of the app |

---

## Stage 5 — Upgrade quality flags (Week 4+)

The current rule-based flags work but have limits. The next level:

| Current | Production upgrade |
|---|---|
| STALE: date arithmetic | + Check gov.uk Content API `change_history` to detect silent updates |
| SUPERSEDED: regex match | + Cross-reference against gov.uk's own `links.superseded_by` JSON field |
| CONTRADICTION: regex | + Use an LLM (GPT-4o via Azure OpenAI) to compare policy values semantically |
| DUPLICATE: cosine similarity | Already production-grade — keep as-is |

---

## Stage 6 — Replace Streamlit (Month 2+)

Streamlit is fine for a hackathon prototype but not for a caseworker tool used in production because:

- No proper auth integration
- No accessibility compliance (WCAG 2.1 AA required for gov.uk tools)
- No offline/print view for tribunal records
- Slow initial load

**Replace with:** React + FastAPI backend, or a GOV.UK Frontend (Nunjucks/Node) app. The Python `src/` layer (`extractor.py`, `indexer.py`, `qa.py`) becomes a REST API — nothing needs rewriting except `app.py`.

---

## Known code improvements before go-live

These were identified during code review and should be addressed before production:

| # | File | Issue | Risk |
|---|---|---|---|
| 1 | extractor.py | Silent error swallowing in `load_all_documents` | High — missing docs invisible to users |
| 2 | extractor.py | TXT date not normalised → STALE flag misses stale docs | High |
| 3 | extractor.py | Document ID fallback breaks SUPERSEDED detection | Medium |
| 4 | extractor.py | Markdown table breaks on escaped pipes `\|` | Low |
| 5 | extractor.py | Acronyms (DHP, UC, LHA) filtered from keywords | Medium |
| 6 | qa.py | STALE threshold hardcoded at 12 months for all doc types | Medium |
| 7 | qa.py | SUPERSEDED regex only matches `DOC-XXX-NNN` format | Medium |
| 8 | indexer.py | `seen_doc_ids` declared but never used — dedup broken | High |
| 9 | indexer.py | No acronym expansion — `"MIF"` / `"LHA"` queries return nothing | High (UX) |

---

## Immediate next step

Fix issues #8 (dedup) and #9 (acronym expansion) and add a `Dockerfile` so the app is container-ready.
