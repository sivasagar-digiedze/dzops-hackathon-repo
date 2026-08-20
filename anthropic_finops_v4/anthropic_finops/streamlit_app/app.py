from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from anthropic_admin.config import MongoConfig
from anthropic_admin.repository.mongo_repository import MongoAnthropicRepository
from pymongo import MongoClient

# Labels
WORKSPACE_DEFAULT_LABEL = "Default Workspace"
APIKEY_DEFAULT_LABEL = "Playground / Console Chat"
ALL_LABEL = "[ALL]"
DEFAULT_LABEL = "Unknown / Not Available"


def get_db():
    cfg = MongoConfig.from_env()

    client = MongoClient(
        cfg.uri,
        serverSelectionTimeoutMS=5000,
    )

    db = client[cfg.database]

    return db, cfg

def load_usage(query: dict) -> pd.DataFrame:
    db, _ = get_db()
    coll = db['anthropic_usage']
    docs = list(coll.find(query))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    return df


def load_costs(query: dict) -> pd.DataFrame:
    db, _ = get_db()
    coll = db['anthropic_costs']
    docs = list(coll.find(query))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    return df


def label_null(val: Any, kind: str = "other") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        if kind == "workspace":
            return WORKSPACE_DEFAULT_LABEL
        if kind == "apikey":
            return APIKEY_DEFAULT_LABEL
        return DEFAULT_LABEL
    return val


def fmt_tokens(n: Any) -> str:
    try:
        n = float(n)
    except Exception:
        return str(n)
    if n >= 1e6:
        return f"{n/1e6:.1f}M"
    if n >= 1e3:
        return f"{n/1e3:.1f}K"
    return f"{int(n):,}"


def fmt_cost(n: Any) -> str:
    try:
        n = float(n)
    except Exception:
        return str(n)
    return f"${n:,.2f}"


st.set_page_config(page_title="Anthropic FinOps Dashboard", layout="wide")
st.title("Anthropic FinOps Dashboard")

try:
    db, mongo_cfg = get_db()
    # quick ping
    db.command("ping")
except Exception as exc:
    st.error(f"Could not connect to MongoDB: {type(exc).__name__}. Check MONGODB_URI in .env.")
    st.stop()

# Date defaults (UTC-aware behavior expressed as naive UTC datetimes)
now = datetime.utcnow()
default_end = now.replace(minute=0, second=0, microsecond=0)
default_start = default_end - timedelta(days=2)

with st.sidebar:
    st.header("Filters & Date Range")
    start_date = st.date_input("Start date (UTC)", value=default_start.date())
    end_date = st.date_input("End date (UTC)", value=default_end.date())
    if start_date > end_date:
        st.error("Start must be on or before End")

    # inclusive range
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    start_iso = start_dt.isoformat() + "Z"
    end_iso = (end_dt + timedelta(seconds=1)).isoformat() + "Z"

    base_query = {"period_start": {"$gte": start_iso, "$lt": end_iso}}

    # Load only the two collections required
    raw_df = load_usage(base_query)
    cost_df = load_costs(base_query)

    # Helper to distinct available values for filters
    def _distinct(df: pd.DataFrame, col: str):
        if df.empty or col not in df.columns:
            return []
        vals = df[col].dropna().unique().tolist()
        return sorted(vals, key=lambda v: str(v))

    st.markdown("---")
    st.subheader("Usage Filters")
    usage_filter_cols = []
    # candidate filters; only show when data exists
    for col, kind in [
        ("workspace_id", "workspace"),
        ("api_key_id", "apikey"),
        ("model", "other"),
        ("pd.context_window", "other"),
        ("service_tier", "other"),
        ("pd.inference_geo", "other"),
        ("pd.speed", "other"),
        ("pd.service_account_id", "other"),
        ("pd.account_id", "other"),
    ]:
        vals = sorted(set(_distinct(raw_df, col)))
        if not vals:
            continue
        opts = [ALL_LABEL]
        # include null placeholder
        opts += [label_null(None, kind)]
        opts += vals
        sel = st.selectbox(col.replace("pd.", ""), opts, key=f"f_{col}")
        if sel != ALL_LABEL:
            usage_filter_cols.append((col, sel, kind))

    st.markdown("---")
    st.subheader("Cost Filters")
    cost_filter_cols = []
    for col in ["workspace_id", "model", "description"]:
        vals = _distinct(cost_df, col)
        if not vals:
            continue
        opts = [ALL_LABEL] + vals
        sel = st.selectbox(f"cost_{col}", opts, key=f"f_cost_{col}")
        if sel != ALL_LABEL:
            cost_filter_cols.append((col, sel))

    st.markdown("---")
    st.caption("Reads only anthropic_usage and anthropic_costs from MongoDB. Dashboard will not modify data.")

# Apply filters
def apply_filters(df: pd.DataFrame, filters):
    out = df.copy()
    for col, sel, kind in filters:
        if col not in out.columns:
            continue
        if sel == label_null(None, kind):
            out = out[out[col].isna()]
        else:
            out = out[out[col] == sel]
    return out


filtered_usage = apply_filters(raw_df, usage_filter_cols) if not raw_df.empty else raw_df
filtered_costs = cost_df.copy()
for col, sel in cost_filter_cols:
    if col not in filtered_costs.columns:
        continue
    if sel == ALL_LABEL:
        continue
    filtered_costs = filtered_costs[filtered_costs[col] == sel]

# Overview / Usage / Cost tabs
tab_overview, tab_usage, tab_cost = st.tabs(["Overview", "Usage", "Cost"])

with tab_overview:
    st.header("Overview")
    st.markdown("High-level summary for selected range and filters.")
    # Usage KPIs
    col1, col2, col3 = st.columns(3)
    if filtered_usage.empty:
        col1.metric("Input Tokens", "0")
        col1.metric("Output Tokens", "0")
        col2.metric("Cache Creation Tokens", "0")
        col2.metric("Cache Read Tokens", "0")
        col3.metric("Total Tokens", "0")
        col3.metric("Total Requests", "0")
    else:
        fu = filtered_usage
        fu['input_tokens'] = fu.get('input_tokens', 0)
        total_input = fu['input_tokens'].sum()
        total_output = fu.get('output_tokens', 0)
        total_output = total_output.sum() if hasattr(total_output, 'sum') else 0
        total_cache_create = fu.get('cache_creation_input_tokens', 0)
        total_cache_create = total_cache_create.sum() if hasattr(total_cache_create, 'sum') else 0
        total_cache_read = fu.get('cache_read_input_tokens', 0)
        total_cache_read = total_cache_read.sum() if hasattr(total_cache_read, 'sum') else 0
        total_tokens = fu['total_tokens'].sum() if 'total_tokens' in fu.columns else total_input + total_output + total_cache_create + total_cache_read
        total_requests = fu['request_count'].sum() if 'request_count' in fu.columns else 0

        col1.metric("Input Tokens", fmt_tokens(total_input))
        col1.metric("Output Tokens", fmt_tokens(total_output))
        col2.metric("Cache Creation Tokens", fmt_tokens(total_cache_create))
        col2.metric("Cache Read Tokens", fmt_tokens(total_cache_read))
        col3.metric("Total Tokens", fmt_tokens(total_tokens))
        col3.metric("Total Requests", f"{int(total_requests):,}")

    # Cost KPIs
    c1, c2, c3, c4 = st.columns(4)
    if filtered_costs.empty:
        c1.metric("Total Cost", "$0.00")
    else:
        fc = filtered_costs
        totals = {}
        totals['total_cost'] = float(fc['total_cost'].sum()) if 'total_cost' in fc.columns else 0.0
        for k in ['token_cost', 'web_search_cost', 'code_execution_cost', 'session_runtime_cost']:
            if k in fc.columns:
                totals[k] = float(fc[k].sum())
        c1.metric("Total Cost", fmt_cost(totals.get('total_cost', 0.0)))
        if 'token_cost' in totals:
            c2.metric("Token Cost", fmt_cost(totals['token_cost']))
        if 'web_search_cost' in totals:
            c3.metric("Web Search Cost", fmt_cost(totals['web_search_cost']))
        if 'code_execution_cost' in totals:
            c4.metric("Code Execution Cost", fmt_cost(totals['code_execution_cost']))

    st.markdown("---")
    st.write("Use the Usage and Cost tabs for detailed charts and tables.")

with tab_usage:
    st.header("Usage")
    if filtered_usage.empty:
        st.info("No usage data available for the selected filters.")
    else:
        dfu = filtered_usage.copy()
        dfu['period_start'] = pd.to_datetime(dfu['period_start'])
        dfu = dfu.sort_values('period_start')

        # Tokens over time (hourly stacked)
        tok_ts = dfu.groupby('period_start')[['input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens']].sum().reset_index()
        tok_ts.fillna(0, inplace=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=tok_ts['period_start'], y=tok_ts['input_tokens'], name='Input'))
        fig.add_trace(go.Bar(x=tok_ts['period_start'], y=tok_ts['output_tokens'], name='Output'))
        fig.add_trace(go.Bar(x=tok_ts['period_start'], y=tok_ts['cache_creation_input_tokens'], name='Cache Creation'))
        fig.add_trace(go.Bar(x=tok_ts['period_start'], y=tok_ts['cache_read_input_tokens'], name='Cache Read'))
        fig.update_layout(barmode='stack', title='Tokens Over Time (Hourly)', xaxis_title='Hour (UTC)', yaxis_title='Tokens')
        st.plotly_chart(fig, use_container_width=True)

        # Total tokens over time
        tok_ts['total_tokens'] = tok_ts[['input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens']].sum(axis=1)
        fig2 = px.line(tok_ts, x='period_start', y='total_tokens', title='Total Tokens Over Time')
        fig2.update_layout(xaxis_title='Hour (UTC)', yaxis_title='Total Tokens')
        st.plotly_chart(fig2, use_container_width=True)

        # Requests over time
        if 'request_count' in dfu.columns:
            req_ts = dfu.groupby('period_start')['request_count'].sum().reset_index()
            figr = px.bar(req_ts, x='period_start', y='request_count', title='Requests Over Time')
            st.plotly_chart(figr, use_container_width=True)

        st.markdown("---")
        st.subheader("Breakdowns")
        b1, b2 = st.columns(2)
        with b1:
            if 'model' in dfu.columns:
                by_model = dfu.groupby('model')['total_tokens'].sum().reset_index().sort_values('total_tokens', ascending=False)
                st.plotly_chart(px.bar(by_model.head(20), x='model', y='total_tokens', title='Usage by Model'), use_container_width=True)
        with b2:
            if 'workspace_id' in dfu.columns:
                dfu['workspace_label'] = dfu['workspace_id'].apply(lambda v: label_null(v, 'workspace'))
                by_ws = dfu.groupby('workspace_label')['total_tokens'].sum().reset_index().sort_values('total_tokens', ascending=False)
                st.plotly_chart(px.bar(by_ws.head(20), x='workspace_label', y='total_tokens', title='Usage by Workspace'), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            ctx_col = 'pd.context_window' if 'pd.context_window' in dfu.columns else ('context_window' if 'context_window' in dfu.columns else None)
            if ctx_col:
                by_ctx = dfu.groupby(ctx_col)['total_tokens'].sum().reset_index()
                st.plotly_chart(px.pie(by_ctx, names=ctx_col, values='total_tokens', title='Usage by Context Window'), use_container_width=True)
        with c2:
            if 'service_tier' in dfu.columns:
                by_tier = dfu.groupby('service_tier')['total_tokens'].sum().reset_index()
                st.plotly_chart(px.bar(by_tier, x='service_tier', y='total_tokens', title='Usage by Service Tier'), use_container_width=True)

        d1, d2 = st.columns(2)
        with d1:
            ig_col = 'pd.inference_geo' if 'pd.inference_geo' in dfu.columns else ('inference_geo' if 'inference_geo' in dfu.columns else None)
            if ig_col:
                by_ig = dfu.groupby(ig_col)['total_tokens'].sum().reset_index()
                st.plotly_chart(px.bar(by_ig, x=ig_col, y='total_tokens', title='Usage by Inference Geo'), use_container_width=True)
        with d2:
            sp_col = 'pd.speed' if 'pd.speed' in dfu.columns else ('speed' if 'speed' in dfu.columns else None)
            if sp_col:
                by_sp = dfu.groupby(sp_col)['total_tokens'].sum().reset_index()
                st.plotly_chart(px.bar(by_sp, x=sp_col, y='total_tokens', title='Usage by Speed'), use_container_width=True)

        # Usage by API key
        if 'api_key_id' in dfu.columns:
            dfu['api_key_label'] = dfu['api_key_id'].apply(lambda v: label_null(v, 'apikey'))
            by_key = dfu.groupby('api_key_label')['total_tokens'].sum().reset_index().sort_values('total_tokens', ascending=False)
            st.plotly_chart(px.bar(by_key.head(30), x='api_key_label', y='total_tokens', title='Usage by API Key'), use_container_width=True)

        st.markdown('### Detailed Usage Records')
        use_cols = ['period_start','period_end','model','workspace_id','api_key_id','pd.context_window','service_tier','pd.inference_geo','pd.speed','input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens','total_tokens','request_count']
        display = [c for c in use_cols if c in dfu.columns]
        table = dfu[display].sort_values('period_start', ascending=False)
        st.dataframe(table, use_container_width=True)
        csv = table.to_csv(index=False)
        st.download_button('Download Usage CSV', data=csv, file_name='anthropic_usage_filtered.csv', mime='text/csv')

with tab_cost:
    st.header('Cost')
    if filtered_costs.empty:
        st.info('No cost data available for the selected filters.')
    else:
        dfc = filtered_costs.copy()
        dfc['period_start'] = pd.to_datetime(dfc['period_start'])
        dfc = dfc.sort_values('period_start')

        # Cost over time (daily buckets)
        if 'total_cost' in dfc.columns:
            cost_ts = dfc.groupby('period_start')['total_cost'].sum().reset_index()
            figc = px.bar(cost_ts, x='period_start', y='total_cost', title='Total Cost Over Time')
            figc.update_layout(xaxis_title='Day (UTC)', yaxis_title='Cost (USD)')
            st.plotly_chart(figc, use_container_width=True)

        # Cost components
        comp_cols = [c for c in ['token_cost','web_search_cost','code_execution_cost','session_runtime_cost'] if c in dfc.columns]
        if comp_cols:
            comp_ts = dfc.groupby('period_start')[comp_cols].sum().reset_index()
            figcomp = go.Figure()
            for c in comp_cols:
                figcomp.add_trace(go.Bar(x=comp_ts['period_start'], y=comp_ts[c], name=c))
            figcomp.update_layout(barmode='stack', title='Cost Components Over Time', xaxis_title='Day (UTC)', yaxis_title='Cost (USD)')
            st.plotly_chart(figcomp, use_container_width=True)

        # By model / workspace / description
        r1, r2 = st.columns(2)
        with r1:
            if 'model' in dfc.columns:
                by_model = dfc.groupby('model')['total_cost'].sum().reset_index().sort_values('total_cost', ascending=False)
                st.plotly_chart(px.bar(by_model.head(20), x='model', y='total_cost', title='Cost by Model'), use_container_width=True)
        with r2:
            if 'workspace_id' in dfc.columns:
                dfc['workspace_label'] = dfc['workspace_id'].apply(lambda v: label_null(v,'workspace'))
                by_ws = dfc.groupby('workspace_label')['total_cost'].sum().reset_index().sort_values('total_cost', ascending=False)
                st.plotly_chart(px.bar(by_ws.head(20), x='workspace_label', y='total_cost', title='Cost by Workspace'), use_container_width=True)

        if 'description' in dfc.columns:
            by_desc = dfc.groupby('description')['total_cost'].sum().reset_index().sort_values('total_cost', ascending=False)
            st.plotly_chart(px.bar(by_desc.head(30), x='description', y='total_cost', title='Cost by Description (top 30)'), use_container_width=True)

        st.markdown('### Detailed Cost Records')
        cost_cols = ['period_start','period_end','model','workspace_id','description','token_cost','web_search_cost','code_execution_cost','session_runtime_cost','total_cost','currency','created_at','deleted_at']
        display_cols = [c for c in cost_cols if c in dfc.columns]
        tablec = dfc[display_cols].sort_values('period_start', ascending=False)
        st.dataframe(tablec, use_container_width=True)
        csvc = tablec.to_csv(index=False)
        st.download_button('Download Costs CSV', data=csvc, file_name='anthropic_costs_filtered.csv', mime='text/csv')

st.caption('This dashboard only reads anthropic_usage and anthropic_costs and does not modify MongoDB data.')
