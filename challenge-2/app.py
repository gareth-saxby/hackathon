"""
Streamlit app — Government Document Search & Data Quality Tool
Challenge 2: Unlocking the Dark Data — DSIT AI Engineering Lab Hackathon 2026

Run with:  streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make src importable when running from challenge-2/
sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import load_all_documents
from src.indexer import DocumentIndex
from src.qa import detect_quality_flags, quality_summary
from src.schema import STALE, SUPERSEDED, MISSING_METADATA, CONTRADICTION, DUPLICATE

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GovDoc Search",
    page_icon="🏛️",
    layout="wide",
)

DATA_DIR = Path(__file__).parent.parent.parent / (
    "ai-engineering-lab-hackathon-london-2026/challenge-2/structured_files"
)

# ---------------------------------------------------------------------------
# Load and cache data
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading documents...")
def load_index() -> tuple[list, DocumentIndex]:
    docs = load_all_documents(str(DATA_DIR))
    index = DocumentIndex(docs)
    detect_quality_flags(docs, index=index)
    return docs, index


docs, index = load_index()

if len(docs) == 0:
    st.error(
        f"No documents loaded. Check that the data folder exists: `{DATA_DIR}`"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🏛️ GovDoc Search")
st.sidebar.caption("Challenge 2 — Unlocking the Dark Data")
st.sidebar.markdown("---")
st.sidebar.metric("Documents loaded", len(docs))
flagged = sum(1 for d in docs if d.quality_flags)
st.sidebar.metric("Documents with quality flags", flagged)
st.sidebar.markdown("---")
tab_choice = st.sidebar.radio(
    "Navigate", ["🔍 Search", "📋 Browse", "⚠️ Data Quality"]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FLAG_LABELS = {
    STALE: ("🕐 Stale", "orange"),
    SUPERSEDED: ("🔄 Superseded", "red"),
    MISSING_METADATA: ("❓ Missing metadata", "grey"),
    CONTRADICTION: ("⚡ Contradiction", "red"),
    DUPLICATE: ("🔁 Duplicate", "purple"),
}


def render_flags(flags):
    for f in flags:
        label, colour = FLAG_LABELS.get(f, (f, "grey"))
        st.markdown(
            f'<span style="background:{colour};color:white;'
            f'padding:2px 8px;border-radius:4px;font-size:0.8em">{label}</span>',
            unsafe_allow_html=True,
        )


def render_status_badge(status):
    colour = {"current": "green", "draft": "orange", "superseded": "red"}.get(
        (status or "").lower(), "grey"
    )
    st.markdown(
        f'<span style="background:{colour};color:white;'
        f'padding:2px 8px;border-radius:4px;font-size:0.8em">{status or "unknown"}</span>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tab: Search
# ---------------------------------------------------------------------------

if tab_choice == "🔍 Search":
    st.title("🔍 Search Government Guidance")
    st.caption(
        "Search across all policy documents. Results show the exact passage "
        "that matches your query, with source and data quality warnings."
    )

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input(
            "Ask a question or enter keywords",
            placeholder="e.g. Is someone with savings of £10k eligible for housing benefit?",
        )
    with col2:
        status_filter = st.selectbox(
            "Filter by status", ["All", "current", "draft", "superseded"]
        )
    with col3:
        all_topics = sorted({
            t for d in docs for raw in d.topics
            for t in (raw if isinstance(raw, list) else [raw])
            if isinstance(t, str) and t.strip()
        })
        topic_filter = st.selectbox("Filter by topic", ["All"] + all_topics)

    if query:
        results = index.search(
            query,
            top_n=8,
            status_filter=None if status_filter == "All" else status_filter,
            topic_filter=None if topic_filter == "All" else topic_filter,
        )

        if not results:
            st.info("No matching passages found. Try different keywords.")
        else:
            st.markdown(f"**{len(results)} result(s)** for: *{query}*")
            st.markdown("---")
            for i, r in enumerate(results):
                relevance = "High" if r.score >= 0.3 else "Medium" if r.score >= 0.1 else "Low"
                with st.expander(
                    f"📄 {r.title}  —  {r.section_heading}  [{relevance} relevance]",
                    expanded=(i == 0),
                ):
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.markdown(f"**Document ID:** `{r.document_id}`")
                        st.markdown(f"**Department:** {r.department or '—'}")
                    with col_b:
                        st.markdown("**Status:**")
                        render_status_badge(r.status)
                    with col_c:
                        st.markdown(
                            f"**Published:** {r.publication_date or '—'}  \n"
                            f"**Updated:** {r.last_updated or '—'}"
                        )
                    st.markdown("**Matching passage:**")
                    st.info(r.passage)
                    # Score bar + matching terms
                    score_pct = int(r.score * 100)
                    st.markdown(
                        f"**Relevance score:** {score_pct}% "
                        f"<progress value='{score_pct}' max='100' "
                        f"style='width:160px;vertical-align:middle'></progress>",
                        unsafe_allow_html=True,
                    )
                    if r.matching_terms:
                        terms_html = " ".join(
                            f'<code style="background:#e8f4f8;padding:1px 5px;'
                            f'border-radius:3px;font-size:0.85em">{t}</code>'
                            for t in r.matching_terms
                        )
                        st.markdown(
                            f"**Matched on:** {terms_html}",
                            unsafe_allow_html=True,
                        )
                    if r.quality_flags:
                        st.markdown("**Warnings:**")
                        render_flags(r.quality_flags)
                    # Citation block — copy-ready reference for caseworker records
                    st.markdown("**Citation:**")
                    citation = (
                        f"{r.document_id} | {r.title} | "
                        f"§ {r.section_heading} | "
                        f"Last updated: {r.last_updated or 'unknown'} | "
                        f"Source: {r.source_file}"
                    )
                    st.code(citation, language=None)

# ---------------------------------------------------------------------------
# Tab: Browse
# ---------------------------------------------------------------------------

elif tab_choice == "📋 Browse":
    st.title("📋 Browse All Documents")
    st.caption("Full corpus overview — click any document to see its sections and metadata.")

    search_filter = st.text_input("Filter by title or ID", placeholder="e.g. housing benefit")

    filtered_docs = [
        d for d in docs
        if not search_filter
        or search_filter.lower() in d.title.lower()
        or search_filter.lower() in d.document_id.lower()
    ]

    st.markdown(f"Showing **{len(filtered_docs)}** of {len(docs)} documents")
    st.markdown("---")

    for doc in filtered_docs:
        flag_summary = " ".join(
            FLAG_LABELS.get(f, (f, "grey"))[0] for f in doc.quality_flags
        )
        expander_label = f"📄 [{doc.document_id}] {doc.title}"
        if doc.quality_flags:
            expander_label += f"  —  {flag_summary}"

        with st.expander(expander_label):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**Department:** {doc.department or '—'}")
                st.markdown(f"**Audience:** {doc.audience or '—'}")
                st.markdown(f"**Topics:** {', '.join(doc.topics) or '—'}")
            with col2:
                st.markdown("**Status:**")
                render_status_badge(doc.status)
                st.markdown(f"**Type:** {doc.document_type or '—'}")
                st.markdown(f"**Version:** {doc.version or '—'}")
            with col3:
                st.markdown(f"**Published:** {doc.publication_date or '—'}")
                st.markdown(f"**Last updated:** {doc.last_updated or '—'}")
                st.markdown(f"**Format:** `{doc.source_format}`")

            if doc.quality_flags:
                st.markdown("**Quality flags:**")
                render_flags(doc.quality_flags)

            if doc.supersedes:
                st.markdown(f"**Supersedes:** `{doc.supersedes}`")
            if doc.related_documents:
                st.markdown(f"**Related:** {', '.join(doc.related_documents)}")

            if doc.sections:
                st.markdown("**Sections:**")
                for s in doc.sections:
                    indent = "&nbsp;" * ((s.level - 1) * 4)
                    st.markdown(
                        f"{indent}{'#' * s.level} {s.heading}",
                        unsafe_allow_html=True,
                    )

            if doc.tables:
                st.markdown(f"**Tables:** {len(doc.tables)} found")
                for i, tbl in enumerate(doc.tables):
                    if tbl.headers and tbl.rows:
                        caption = tbl.caption or f"Table {i + 1}"
                        st.caption(caption)
                        st.dataframe(
                            pd.DataFrame(tbl.rows, columns=tbl.headers[:len(tbl.rows[0])])
                            if tbl.rows else pd.DataFrame(columns=tbl.headers),
                            use_container_width=True,
                        )

# ---------------------------------------------------------------------------
# Tab: Data Quality
# ---------------------------------------------------------------------------

elif tab_choice == "⚠️ Data Quality":
    st.title("⚠️ Data Quality Dashboard")
    st.caption(
        "Automated flags detected across the corpus. "
        "Use this to identify stale, superseded, or incomplete documents before relying on them."
    )

    summary = quality_summary(docs, index=index)
    duplicate_pairs = summary.get("_duplicate_pairs", [])

    # Top-level metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🕐 Stale", len(summary[STALE]))
    c2.metric("🔄 Superseded", len(summary[SUPERSEDED]))
    c3.metric("❓ Missing metadata", len(summary[MISSING_METADATA]))
    c4.metric("⚡ Contradictions", len(summary[CONTRADICTION]))
    c5.metric("🔁 Duplicates", len(summary.get(DUPLICATE, [])))

    st.markdown("---")

    flag_config = [
        (STALE,            "🕐 Stale documents",
         "Status is marked *current* but last updated more than 12 months ago."),
        (SUPERSEDED,       "🔄 Superseded documents",
         "Another document in the corpus explicitly supersedes these."),
        (MISSING_METADATA, "❓ Missing metadata",
         "One or more required fields (title, department, publication date) are absent."),
        (CONTRADICTION,    "⚡ Contradictory values",
         "The same policy value (e.g. capital threshold) appears with different amounts across documents."),
    ]

    for flag, heading, description in flag_config:
        items = summary[flag]
        with st.expander(f"{heading}  ({len(items)} document(s))", expanded=bool(items)):
            st.caption(description)
            if not items:
                st.success("No issues found.")
            else:
                for item in items:
                    doc = next((d for d in docs if d.document_id == item["document_id"]), None)
                    col_a, col_b, col_c = st.columns([2, 1, 1])
                    with col_a:
                        st.markdown(f"**{item['title']}**  \n`{item['document_id']}`")
                    with col_b:
                        if doc:
                            render_status_badge(doc.status)
                    with col_c:
                        if doc:
                            st.markdown(
                                f"Updated: {doc.last_updated or '—'}  \n"
                                f"File: `{doc.source_file}`"
                            )
                    st.markdown("---")

    # Duplicate pairs section
    with st.expander(
        f"🔁 Near-duplicate document pairs  ({len(duplicate_pairs)} pair(s))",
        expanded=bool(duplicate_pairs),
    ):
        st.caption(
            "Document pairs with cosine similarity ≥ 85%. "
            "These may contain redundant or overlapping content."
        )
        if not duplicate_pairs:
            st.success("No near-duplicate pairs found.")
        else:
            for doc_id_a, doc_id_b, sim in duplicate_pairs:
                doc_a = next((d for d in docs if d.document_id == doc_id_a), None)
                doc_b = next((d for d in docs if d.document_id == doc_id_b), None)
                col_x, col_sim, col_y = st.columns([5, 1, 5])
                with col_x:
                    st.markdown(
                        f"**{doc_a.title if doc_a else doc_id_a}**  \n`{doc_id_a}`"
                    )
                with col_sim:
                    st.markdown(
                        f"<div style='text-align:center;padding-top:8px'>"
                        f"<b>{int(sim * 100)}%</b><br/><small>similar</small></div>",
                        unsafe_allow_html=True,
                    )
                with col_y:
                    st.markdown(
                        f"**{doc_b.title if doc_b else doc_id_b}**  \n`{doc_id_b}`"
                    )
                st.markdown("---")
