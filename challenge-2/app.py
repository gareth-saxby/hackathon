"""
app.py — Streamlit UI for the Dark Data Challenge.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — data lives in challenge-info/data/structured_files relative
# to the hackathon root, which is two levels above this file's directory.
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
HACKATHON_ROOT = APP_DIR.parent  # hackathon/

DATA_DIR = HACKATHON_ROOT / "challenge-info" / "data" / "structured_files"
EXTRACTED_DIR = APP_DIR / "data" / "extracted"

# Allow override via environment variable
import os
if os.environ.get("DATA_DIR"):
    DATA_DIR = Path(os.environ["DATA_DIR"])

sys.path.insert(0, str(APP_DIR))

from src.extractor import extract_all, load_extracted, save_extracted
from src.indexer import DocumentIndex, _effective_status
from src.schema import QualityFlag
from src.qa import ask

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Dark Data Explorer",
    page_icon="🔍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Extracting and indexing documents…")
def load_index() -> DocumentIndex:
    if EXTRACTED_DIR.exists() and any(EXTRACTED_DIR.glob("*.json")):
        docs = load_extracted(EXTRACTED_DIR)
    else:
        if not DATA_DIR.exists():
            st.error(
                f"Data directory not found: `{DATA_DIR}`\n\n"
                "Set the `DATA_DIR` environment variable to the folder containing "
                "the structured files."
            )
            st.stop()
        docs = extract_all(DATA_DIR)
        save_extracted(docs, EXTRACTED_DIR)

    idx = DocumentIndex()
    idx.build(docs)
    return idx


index = load_index()
all_docs = index.documents

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🔍 Dark Data Explorer")
st.sidebar.caption(f"{len(all_docs)} documents loaded")

page = st.sidebar.radio(
    "Navigate",
    ["Search", "Browse", "Data Quality"],
    index=0,
)

if st.sidebar.button("♻️ Re-extract documents"):
    import shutil
    if EXTRACTED_DIR.exists():
        shutil.rmtree(EXTRACTED_DIR)
    st.cache_resource.clear()
    st.rerun()

# ---------------------------------------------------------------------------
# Helper: quality flag badges
# ---------------------------------------------------------------------------

FLAG_COLOURS = {
    "STALE": "🟡",
    "SUPERSEDED": "🔴",
    "MISSING_METADATA": "🟠",
    "CONTRADICTION": "🟣",
}

FLAG_LABELS = {
    "STALE": "STALE — may be out of date",
    "SUPERSEDED": "SUPERSEDED — newer version exists",
    "MISSING_METADATA": "MISSING METADATA",
    "CONTRADICTION": "CONTRADICTION — value conflicts with another document",
}


def flag_badges(flags: list) -> str:
    return " ".join(
        f"{FLAG_COLOURS.get(f, '⚪')} `{f}`" for f in flags
    )


# ---------------------------------------------------------------------------
# Search tab
# ---------------------------------------------------------------------------

if page == "Search":
    st.title("Search Government Guidance")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input("Enter your question or keywords", placeholder="e.g. housing benefit capital limit")
    with col2:
        all_topics = ["(all topics)"] + index.get_all_topics()
        topic_filter = st.selectbox("Filter by topic", all_topics)
        topic_filter = None if topic_filter == "(all topics)" else topic_filter
    with col3:
        status_options = ["(any status)", "current", "stale", "superseded"]
        status_filter = st.selectbox("Filter by status", status_options)
        status_filter = None if status_filter == "(any status)" else status_filter

    top_n = st.slider("Max results", min_value=3, max_value=20, value=10)

    if query:
        results = index.search(
            query,
            top_n=top_n,
            topic_filter=topic_filter,
            status_filter=status_filter,
        )
        st.caption(f"**{len(results)}** result(s) for: _{query}_")

        if not results:
            st.info("No matching passages found. Try different keywords or remove filters.")
        else:
            for i, r in enumerate(results, 1):
                eff_status = _effective_status(
                    next(d for d in all_docs if d.document_id == r.document_id)
                )
                status_icon = {"current": "🟢", "stale": "🟡", "superseded": "🔴"}.get(
                    eff_status, "⚪"
                )

                with st.expander(
                    f"{i}. {r.title} — *{r.section_heading}*  {status_icon}",
                    expanded=(i == 1),
                ):
                    # Inline quality warnings (FR-15)
                    if r.quality_flags:
                        for f in r.quality_flags:
                            st.warning(
                                f"{FLAG_COLOURS.get(f, '⚪')} {FLAG_LABELS.get(f, f)}"
                            )

                    st.markdown(f"**Passage:**")
                    # Highlight query terms in passage
                    highlighted = r.passage
                    for word in query.split():
                        if len(word) > 2:
                            highlighted = highlighted.replace(
                                word,
                                f"**{word}**",
                            )
                    st.markdown(f"> {highlighted}")

                    cols = st.columns(4)
                    cols[0].metric("Document ID", r.document_id)
                    cols[1].metric("Status", eff_status.upper())
                    cols[2].metric("Published", r.publication_date or "Unknown")
                    cols[3].metric("Relevance", f"{r.score:.2%}")

                    if r.topics:
                        st.caption("Topics: " + ", ".join(r.topics))


# ---------------------------------------------------------------------------
# Browse tab
# ---------------------------------------------------------------------------

elif page == "Browse":
    st.title("Browse Documents")

    # Summary stats
    total = len(all_docs)
    flagged = sum(1 for d in all_docs if d.quality_flags)
    cols = st.columns(4)
    cols[0].metric("Total documents", total)
    cols[1].metric("Current", sum(1 for d in all_docs if (d.status or "").lower() == "current"))
    cols[2].metric("Flagged", flagged)
    cols[3].metric("Superseded", sum(
        1 for d in all_docs
        if QualityFlag.SUPERSEDED in d.quality_flags or (d.status or "").lower() == "superseded"
    ))

    st.divider()

    # Filters
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        domain_opts = ["All domains", "Housing & Benefits (HB)", "Small Business (SB)"]
        domain = st.selectbox("Domain", domain_opts)
    with f_col2:
        flag_opts = ["All", "Flagged only", "Clean only"]
        flag_filter = st.selectbox("Quality", flag_opts)

    def _domain_match(doc, domain):
        if domain == "All domains":
            return True
        prefix = "DOC-HB-" if "HB" in domain else "DOC-SB-"
        return doc.document_id.startswith(prefix)

    def _flag_match(doc, flag_filter):
        if flag_filter == "All":
            return True
        if flag_filter == "Flagged only":
            return bool(doc.quality_flags)
        return not doc.quality_flags

    filtered = [
        d for d in all_docs
        if _domain_match(d, domain) and _flag_match(d, flag_filter)
    ]

    st.caption(f"Showing {len(filtered)} of {total} documents")

    for doc in filtered:
        eff_status = _effective_status(doc)
        status_icon = {"current": "🟢", "stale": "🟡", "superseded": "🔴"}.get(eff_status, "⚪")

        with st.expander(
            f"{status_icon} **{doc.document_id}** — {doc.title}",
            expanded=False,
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Status", eff_status.upper())
            c2.metric("Published", doc.publication_date or "—")
            c3.metric("Last updated", doc.last_updated or "—")
            c4.metric("Format", doc.source_format.upper())

            if doc.department:
                st.caption(f"**Department:** {doc.department}")
            if doc.audience:
                st.caption(f"**Audience:** {doc.audience}")
            if doc.topics:
                st.caption(f"**Topics:** {', '.join(doc.topics)}")
            if doc.version:
                st.caption(f"**Version:** {doc.version}")
            if doc.supersedes:
                st.caption(f"**Supersedes:** {doc.supersedes}")
            if doc.related_documents:
                st.caption(f"**Related:** {', '.join(doc.related_documents)}")

            # Quality badges
            if doc.quality_flags:
                st.markdown("**Quality flags:** " + flag_badges([f.value for f in doc.quality_flags]))

            # Section list
            if doc.sections:
                st.markdown("**Sections:**")
                for s in doc.sections[:8]:
                    indent = "  " * (s.level - 1)
                    st.markdown(f"{indent}- {s.heading}")
                if len(doc.sections) > 8:
                    st.caption(f"… and {len(doc.sections) - 8} more sections")


# ---------------------------------------------------------------------------
# Data Quality tab
# ---------------------------------------------------------------------------

elif page == "Data Quality":
    st.title("Data Quality Dashboard")

    stale_docs = [d for d in all_docs if QualityFlag.STALE in d.quality_flags]
    superseded_docs = [d for d in all_docs if QualityFlag.SUPERSEDED in d.quality_flags]
    missing_meta_docs = [d for d in all_docs if QualityFlag.MISSING_METADATA in d.quality_flags]
    contradiction_docs = [d for d in all_docs if QualityFlag.CONTRADICTION in d.quality_flags]
    clean_docs = [d for d in all_docs if not d.quality_flags]

    # Summary metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🟡 Stale", len(stale_docs))
    c2.metric("🔴 Superseded", len(superseded_docs))
    c3.metric("🟠 Missing Metadata", len(missing_meta_docs))
    c4.metric("🟣 Contradictions", len(contradiction_docs))
    c5.metric("🟢 Clean", len(clean_docs))

    st.divider()

    def _doc_row(doc):
        eff = _effective_status(doc)
        badges = " ".join(FLAG_COLOURS.get(f.value, "⚪") for f in doc.quality_flags)
        st.markdown(
            f"- **{doc.document_id}** — {doc.title}  \n"
            f"  {badges}  ·  Published: {doc.publication_date or '?'}  "
            f"·  Last updated: {doc.last_updated or '?'}  "
            f"·  Status: `{eff}`"
        )

    if stale_docs:
        with st.expander(f"🟡 Stale documents ({len(stale_docs)})", expanded=True):
            st.caption(
                "Marked `current` but last updated more than 12 months ago."
            )
            for doc in stale_docs:
                _doc_row(doc)

    if superseded_docs:
        with st.expander(f"🔴 Superseded documents ({len(superseded_docs)})", expanded=True):
            st.caption(
                "Another document in the corpus declares it supersedes this one."
            )
            for doc in superseded_docs:
                _doc_row(doc)

    if missing_meta_docs:
        with st.expander(f"🟠 Missing metadata ({len(missing_meta_docs)})", expanded=True):
            st.caption("One or more required fields (title, department, publication_date) are absent.")
            for doc in missing_meta_docs:
                missing = [
                    f for f in ("title", "department", "publication_date")
                    if not getattr(doc, f, None)
                ]
                st.markdown(
                    f"- **{doc.document_id}** — {doc.title}  \n"
                    f"  Missing: `{'`, `'.join(missing)}`"
                )

    if contradiction_docs:
        with st.expander(f"🟣 Contradictions ({len(contradiction_docs)})", expanded=True):
            st.caption(
                "Documents where a named policy value differs from the same value in another document."
            )
            for doc in contradiction_docs:
                _doc_row(doc)

    if not any([stale_docs, superseded_docs, missing_meta_docs, contradiction_docs]):
        st.success("No quality issues detected in the corpus.")

    st.divider()
    st.subheader("Full issue log")
    rows = []
    for doc in all_docs:
        for flag in doc.quality_flags:
            rows.append(
                {
                    "Document ID": doc.document_id,
                    "Title": doc.title,
                    "Flag": flag.value,
                    "Status": doc.status or "—",
                    "Published": doc.publication_date or "—",
                    "Last updated": doc.last_updated or "—",
                }
            )
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No issues found.")
