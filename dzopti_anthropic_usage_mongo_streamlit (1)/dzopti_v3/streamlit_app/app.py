"""
Dzopti — Anthropic Daily Token Usage dashboard.

Reads ONLY from MongoDB (dzops_core.demo_tokens_usage). Never calls the
Anthropic API directly — per the architecture, Anthropic -> Collector ->
Normalize -> MongoDB -> Streamlit is a one-way pipeline; this file is
the last box.

Run:
    streamlit run streamlit_app/app.py
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from pymongo import MongoClient

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anthropic_admin.config import MongoConfig  # noqa: E402

st.set_page_config(page_title="Dzopti — Anthropic Token Usage", layout="wide")


# ---------------------------------------------------------------------------
# Data access (cached — never re-queries Mongo more than necessary)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_collection():
    config = MongoConfig.from_hardcoded()
    client = MongoClient(config.uri, serverSelectionTimeoutMS=5000)
    return client[config.database][config.usage_collection]


@st.cache_data(ttl=60)
def load_date_bounds() -> tuple[date, date]:
    collection = get_collection()
    earliest = collection.find_one(sort=[("period_start", 1)])
    latest = collection.find_one(sort=[("period_start", -1)])
    if not earliest or not latest:
        today = date.today()
        return today - timedelta(days=18), today
    start = datetime.fromisoformat(earliest["period_start"].replace("Z", "+00:00")).date()
    end = datetime.fromisoformat(latest["period_start"].replace("Z", "+00:00")).date()
    return start, end


@st.cache_data(ttl=60)
def load_distinct_values(field: str, start_iso: str, end_iso: str) -> list:
    collection = get_collection()
    values = collection.distinct(
        field, {"period_start": {"$gte": start_iso}, "period_end": {"$lte": end_iso}}
    )
    return sorted([v for v in values if v is not None], key=str)


@st.cache_data(ttl=60)
def load_usage(
    start_iso: str,
    end_iso: str,
    workspaces: tuple,
    api_keys: tuple,
    models: tuple,
    service_tiers: tuple,
) -> pd.DataFrame:
    """
    One efficient Mongo query: a single find() with all filters combined
    server-side, only the fields the dashboard actually uses are
    projected back — no full-document, no full-collection load into
    Streamlit memory.
    """
    collection = get_collection()
    query: dict = {"period_start": {"$gte": start_iso}, "period_end": {"$lte": end_iso}}
    if workspaces:
        query["workspace_id"] = {"$in": list(workspaces)}
    if api_keys:
        query["api_key_id"] = {"$in": list(api_keys)}
    if models:
        query["model"] = {"$in": list(models)}
    if service_tiers:
        query["service_tier"] = {"$in": list(service_tiers)}

    projection = {
        "period_start": 1, "period_end": 1, "workspace_id": 1, "api_key_id": 1,
        "model": 1, "service_tier": 1, "input_tokens": 1, "output_tokens": 1,
        "cache_creation_input_tokens": 1, "cache_read_input_tokens": 1,
        "total_tokens": 1, "provider_data": 1,
    }
    cursor = collection.find(query, projection)
    rows = list(cursor)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["period_start"]).dt.date
    for col in ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "total_tokens"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["inference_geo"] = df["provider_data"].apply(lambda p: (p or {}).get("inference_geo"))
    df["web_search_requests"] = df["provider_data"].apply(lambda p: (p or {}).get("web_search_requests"))
    return df


def compute_usage_id(record: dict) -> str:
    """Mirrors anthropic_admin.repository.mongo_repository.usage_record_id exactly."""
    context_window = (record.get("provider_data") or {}).get("context_window")
    parts = (
        record.get("provider"), record.get("organization_id"),
        record.get("period_start"), record.get("period_end"),
        record.get("workspace_id"), record.get("api_key_id"),
        record.get("model"), record.get("service_tier"), context_window,
    )
    normalized = json.dumps(parts, sort_keys=False, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.title("Dzopti — Anthropic Daily Token Usage")

try:
    min_date, max_date = load_date_bounds()
except Exception as exc:
    st.error(f"Could not connect to MongoDB: {type(exc).__name__}. Check anthropic_admin/config.py MONGODB_URI.")
    st.stop()

st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

start_iso = f"{start_date.isoformat()}T00:00:00Z"
end_iso = f"{(end_date + timedelta(days=1)).isoformat()}T00:00:00Z"

workspace_options = load_distinct_values("workspace_id", start_iso, end_iso)
api_key_options = load_distinct_values("api_key_id", start_iso, end_iso)
model_options = load_distinct_values("model", start_iso, end_iso)
tier_options = load_distinct_values("service_tier", start_iso, end_iso)

selected_workspaces = st.sidebar.multiselect("Workspace", workspace_options)
selected_api_keys = st.sidebar.multiselect("API Key", api_key_options)
selected_models = st.sidebar.multiselect("Model", model_options)
selected_tiers = st.sidebar.multiselect("Service Tier", tier_options)

df = load_usage(
    start_iso, end_iso,
    tuple(selected_workspaces), tuple(selected_api_keys), tuple(selected_models), tuple(selected_tiers),
)

if df.empty:
    st.warning("No usage documents match the current filters/date range. Run the collector first: `python3 -m scripts.collect_and_store`")
    st.stop()

# ---------------------------------------------------------------------------
# Overall totals
# ---------------------------------------------------------------------------

st.subheader("Overall usage")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Input Tokens", f"{int(df['input_tokens'].sum()):,}")
c2.metric("Total Output Tokens", f"{int(df['output_tokens'].sum()):,}")
c3.metric("Total Cache Creation Tokens", f"{int(df['cache_creation_input_tokens'].sum()):,}")
c4.metric("Total Cache Read Tokens", f"{int(df['cache_read_input_tokens'].sum()):,}")
c5.metric("Total Tokens", f"{int(df['total_tokens'].sum()):,}")

# ---------------------------------------------------------------------------
# Daily usage graph
# ---------------------------------------------------------------------------

st.subheader("Daily usage")
daily = df.groupby("date")[["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]].sum().reset_index()
daily_long = daily.melt(id_vars="date", var_name="token_type", value_name="tokens")
fig_daily = px.line(daily_long, x="date", y="tokens", color="token_type", markers=True, title="Daily token usage")
st.plotly_chart(fig_daily, use_container_width=True)
st.caption(
    "Query: `demo_tokens_usage.find({period_start: {$gte, $lte}, ...filters})`, "
    "grouped client-side by `date` (derived from `period_start`), summed per token-type column."
)

# ---------------------------------------------------------------------------
# By workspace / API key / model / service tier
# ---------------------------------------------------------------------------

def _breakdown(df: pd.DataFrame, group_col: str, title: str) -> None:
    st.subheader(title)
    grouped = (
        df.groupby(group_col, dropna=False)[["input_tokens", "output_tokens", "total_tokens"]]
        .sum()
        .reset_index()
        .sort_values("total_tokens", ascending=False)
    )
    grouped[group_col] = grouped[group_col].fillna("(null)")
    col_table, col_chart = st.columns([1, 1])
    with col_table:
        st.dataframe(grouped, use_container_width=True, hide_index=True)
    with col_chart:
        fig = px.bar(grouped, x=group_col, y="total_tokens", title=f"Total tokens by {group_col}")
        st.plotly_chart(fig, use_container_width=True)


_breakdown(df, "workspace_id", "Usage by workspace")
_breakdown(df, "api_key_id", "Usage by API key")
_breakdown(df, "model", "Usage by model")

st.subheader("Usage by service tier")
tier_grouped = df.groupby("service_tier", dropna=False)[["total_tokens"]].sum().reset_index()
tier_grouped["service_tier"] = tier_grouped["service_tier"].fillna("(null)")
st.plotly_chart(px.pie(tier_grouped, names="service_tier", values="total_tokens", title="Token share by service tier"), use_container_width=True)

# ---------------------------------------------------------------------------
# Inference geography (only shown if present in the data)
# ---------------------------------------------------------------------------

if df["inference_geo"].notna().any():
    st.subheader("Usage by inference geography")
    geo_grouped = df.groupby("inference_geo", dropna=False)[["total_tokens"]].sum().reset_index()
    st.plotly_chart(px.bar(geo_grouped, x="inference_geo", y="total_tokens"), use_container_width=True)
else:
    st.caption("Inference geography: not present in the stored usage documents for this range (Anthropic did not return it for the current grouping).")

# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------

if df["web_search_requests"].notna().any():
    st.subheader("Web search requests")
    total_ws = pd.to_numeric(df["web_search_requests"], errors="coerce").fillna(0).sum()
    st.metric("Total web search requests", f"{int(total_ws):,}")
    ws_daily = df.copy()
    ws_daily["web_search_requests"] = pd.to_numeric(ws_daily["web_search_requests"], errors="coerce").fillna(0)
    ws_daily = ws_daily.groupby("date")[["web_search_requests"]].sum().reset_index()
    st.plotly_chart(px.line(ws_daily, x="date", y="web_search_requests", markers=True), use_container_width=True)
else:
    st.caption("Web search requests: not present in the stored usage documents for this range.")

# ---------------------------------------------------------------------------
# Raw -> Normalized -> MongoDB inspection
# ---------------------------------------------------------------------------

with st.expander("Inspect: Raw API response -> Normalized record -> Stored MongoDB document"):
    st.write(
        "Upload the local JSON file written by `scripts/collect_and_store.py` "
        "(default name: `anthropic_normalized_result.json`) to compare a single "
        "usage record across all three stages."
    )
    uploaded = st.file_uploader("Collector output JSON", type="json")
    if uploaded is not None:
        result_json = json.load(uploaded)
        usage_list = result_json.get("usage", [])
        if not usage_list:
            st.info("This file has no usage records.")
        else:
            labels = [
                f"{u['period_start']} | ws={u['workspace_id']} | key={u['api_key_id']} | model={u['model']}"
                for u in usage_list
            ]
            idx = st.selectbox("Pick a usage record", range(len(labels)), format_func=lambda i: labels[i])
            chosen = usage_list[idx]

            col_raw, col_norm, col_doc = st.columns(3)

            with col_norm:
                st.markdown("**Normalized record**")
                st.json(chosen)

            with col_raw:
                st.markdown("**Matching raw Anthropic bucket result**")
                raw_pages = (result_json.get("raw_usage") or {}).get("pages", [])
                match = None
                for page in raw_pages:
                    for bucket in page.get("response", {}).get("data", []):
                        if bucket.get("starting_at") != chosen["period_start"]:
                            continue
                        for r in bucket.get("results", []):
                            if (
                                r.get("workspace_id") == chosen["workspace_id"]
                                and r.get("api_key_id") == chosen["api_key_id"]
                                and r.get("model") == chosen["model"]
                            ):
                                match = r
                                break
                if match:
                    st.json(match)
                else:
                    st.info("No exact raw match found (unexpected — check raw_usage.pages in the file).")

            with col_doc:
                st.markdown("**Stored MongoDB document**")
                doc_id = compute_usage_id(chosen)
                stored = get_collection().find_one({"_id": doc_id})
                if stored:
                    st.json(stored)
                else:
                    st.info("Not found in MongoDB yet — run scripts/collect_and_store.py without --skip-mongo.")
