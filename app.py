"""
Personal Finance Manager — Web App
Streamlit dashboard with Claude AI analysis
"""

import os
import io
import json
import tempfile
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from anthropic import Anthropic

from parser import parse_statement
from categorizer import tag_dataframe

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Finance Manager",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.main { background: #0f0f13; }

.metric-card {
    background: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
}
.metric-card .label {
    font-size: 0.78rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}
.metric-card .value {
    font-size: 1.8rem;
    font-weight: 600;
    color: #f0f0f0;
    font-family: 'DM Mono', monospace;
}
.metric-card .sub {
    font-size: 0.75rem;
    color: #666;
    margin-top: 0.3rem;
}

.section-header {
    font-size: 0.72rem;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #2a2a3a;
}

.ai-bubble {
    background: #1a1a24;
    border: 1px solid #2a2a3a;
    border-left: 3px solid #7c6fff;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin: 0.75rem 0;
    font-size: 0.95rem;
    line-height: 1.7;
    color: #d0d0e0;
}
.user-bubble {
    background: #16202e;
    border: 1px solid #1e3048;
    border-left: 3px solid #3b9eff;
    border-radius: 12px;
    padding: 1rem 1.5rem;
    margin: 0.75rem 0;
    font-size: 0.95rem;
    color: #b0c8e8;
}

.stButton > button {
    background: #7c6fff;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.5rem;
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: #9b8fff;
    transform: translateY(-1px);
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    color: #e0e0f0;
    font-family: 'DM Sans', sans-serif;
}

div[data-testid="stSidebar"] {
    background: #0d0d15;
    border-right: 1px solid #1e1e2e;
}

.upload-hint {
    font-size: 0.8rem;
    color: #666;
    margin-top: 0.5rem;
}

.tag-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ── Color palette for categories ──────────────────────────────────────────────
CAT_COLORS = {
    "Food & Drink":   "#ff6b6b",
    "Travel":         "#4ecdc4",
    "Shopping":       "#ffe66d",
    "Health":         "#a8e6cf",
    "Subscriptions":  "#c3a6ff",
    "Entertainment":  "#ffa07a",
    "Services":       "#87ceeb",
    "Income":         "#69db7c",
    "Transfer":       "#b0b0b0",
    "Other":          "#555577",
}

# ── Session state ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Finance Manager")
    st.markdown("---")

    # API Key
    st.markdown("**Anthropic API Key**")
    api_key_input = st.text_input(
        "API Key",
        value=st.session_state.api_key,
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if api_key_input:
        st.session_state.api_key = api_key_input

    st.markdown("---")

    # File upload
    st.markdown("**Upload Statement**")
    uploaded = st.file_uploader(
        "Upload",
        type=["csv", "xlsx", "xls", "pdf"],
        label_visibility="collapsed",
    )
    st.markdown('<p class="upload-hint">Supports TD, CIBC, Krung Thai · CSV, Excel, PDF</p>', unsafe_allow_html=True)

    if uploaded:
        bank = st.selectbox(
            "Bank / Format",
            ["auto", "td_cibc", "krung_thai", "generic"],
            format_func=lambda x: {
                "auto": "🔍 Auto-detect",
                "td_cibc": "🍁 TD / CIBC (CAD)",
                "krung_thai": "🇹🇭 Krung Thai (THB)",
                "generic": "🌐 Generic",
            }[x],
        )
        currency_override = st.text_input("Currency override (optional)", placeholder="e.g. THB, CAD, USD")

        if st.button("📊 Parse Statement", use_container_width=True):
            with st.spinner("Parsing..."):
                try:
                    suffix = "." + uploaded.name.split(".")[-1].lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded.read())
                        tmp_path = tmp.name

                    df = parse_statement(
                        tmp_path,
                        bank=bank,
                        currency=currency_override.strip() or None,
                    )
                    df = tag_dataframe(df)
                    st.session_state.df = df
                    st.session_state.messages = []
                    st.success(f"✅ {len(df)} transactions loaded")
                except Exception as e:
                    st.error(f"Parse error: {e}")

    st.markdown("---")

    if st.session_state.df is not None:
        df = st.session_state.df
        st.markdown(f"**{len(df)} transactions**")
        st.markdown(f"📅 {df['date'].min().strftime('%b %d')} – {df['date'].max().strftime('%b %d, %Y')}")
        st.markdown(f"🏦 {df['bank'].iloc[0].upper()}")

        if st.button("🗑️ Clear data", use_container_width=True):
            st.session_state.df = None
            st.session_state.messages = []
            st.rerun()

# ── Main content ──────────────────────────────────────────────────────────────
if st.session_state.df is None:
    # Landing
    st.markdown("# Personal Finance Manager")
    st.markdown("Upload a bank statement in the sidebar to get started.")
    st.markdown("")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **📂 Upload any format**
        CSV, Excel, or PDF from TD, CIBC, Krung Thai, or any bank
        """)
    with col2:
        st.markdown("""
        **📊 Instant analysis**
        Spending breakdown by category, trends, and top merchants
        """)
    with col3:
        st.markdown("""
        **🤖 Ask Claude**
        Chat with AI about your spending — get personalized suggestions
        """)
    st.stop()

df = st.session_state.df

# ── KPI row ───────────────────────────────────────────────────────────────────
spent   = abs(df[df["amount"] < 0]["amount"].sum())
received = df[df["amount"] > 0]["amount"].sum()
net     = df["amount"].sum()
txn_count = len(df[df["amount"] < 0])
currency = df["currency"].iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="metric-card">
        <div class="label">Total Spent</div>
        <div class="value" style="color:#ff6b6b">{currency} {spent:,.2f}</div>
        <div class="sub">{txn_count} transactions</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-card">
        <div class="label">Total Received</div>
        <div class="value" style="color:#69db7c">{currency} {received:,.2f}</div>
        <div class="sub">payments & credits</div>
    </div>""", unsafe_allow_html=True)
with c3:
    net_color = "#69db7c" if net >= 0 else "#ff6b6b"
    net_sign  = "+" if net >= 0 else ""
    st.markdown(f"""<div class="metric-card">
        <div class="label">Net Balance</div>
        <div class="value" style="color:{net_color}">{net_sign}{currency} {net:,.2f}</div>
        <div class="sub">income minus spending</div>
    </div>""", unsafe_allow_html=True)
with c4:
    avg = spent / txn_count if txn_count else 0
    st.markdown(f"""<div class="metric-card">
        <div class="label">Avg Transaction</div>
        <div class="value">{currency} {avg:,.2f}</div>
        <div class="sub">per purchase</div>
    </div>""", unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Spending Breakdown</p>', unsafe_allow_html=True)

debits = df[df["amount"] < 0].copy()
debits["amount_abs"] = debits["amount"].abs()

col_left, col_right = st.columns([1, 1])

with col_left:
    cat_totals = debits.groupby("category")["amount_abs"].sum().reset_index()
    cat_totals = cat_totals.sort_values("amount_abs", ascending=False)
    colors = [CAT_COLORS.get(c, "#555577") for c in cat_totals["category"]]

    fig_pie = go.Figure(go.Pie(
        labels=cat_totals["category"],
        values=cat_totals["amount_abs"],
        marker_colors=colors,
        hole=0.55,
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0d0",
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(font=dict(size=12)),
        height=320,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    fig_bar = go.Figure(go.Bar(
        x=cat_totals["amount_abs"],
        y=cat_totals["category"],
        orientation="h",
        marker_color=colors,
        text=[f"{currency} {v:,.0f}" for v in cat_totals["amount_abs"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>",
    ))
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0d0",
        margin=dict(t=10, b=10, l=10, r=120),
        xaxis=dict(showgrid=False, visible=False),
        yaxis=dict(showgrid=False),
        height=320,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ── Daily spending trend ───────────────────────────────────────────────────────
st.markdown('<p class="section-header">Daily Spending Trend</p>', unsafe_allow_html=True)

daily = debits.groupby("date")["amount_abs"].sum().reset_index()
fig_line = go.Figure()
fig_line.add_trace(go.Scatter(
    x=daily["date"], y=daily["amount_abs"],
    mode="lines+markers",
    line=dict(color="#7c6fff", width=2),
    marker=dict(size=6, color="#7c6fff"),
    fill="tozeroy",
    fillcolor="rgba(124,111,255,0.1)",
    hovertemplate="<b>%{x|%b %d}</b><br>%{y:,.2f}<extra></extra>",
))
fig_line.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#c0c0d0",
    margin=dict(t=10, b=10, l=10, r=10),
    xaxis=dict(showgrid=False, color="#666"),
    yaxis=dict(showgrid=True, gridcolor="#1e1e2e", color="#666"),
    height=220,
)
st.plotly_chart(fig_line, use_container_width=True)

# ── Top merchants ──────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Top Merchants</p>', unsafe_allow_html=True)

top_merch = (
    debits.groupby("description")["amount_abs"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
top_merch.columns = ["Merchant", f"Total ({currency})"]
top_merch[f"Total ({currency})"] = top_merch[f"Total ({currency})"].map(lambda x: f"{x:,.2f}")
st.dataframe(top_merch, use_container_width=True, hide_index=True)

# ── Full transaction table ─────────────────────────────────────────────────────
st.markdown('<p class="section-header">All Transactions</p>', unsafe_allow_html=True)

col_f1, col_f2 = st.columns([2, 1])
with col_f1:
    search = st.text_input("Search transactions", placeholder="e.g. Uber, coffee, Amazon...")
with col_f2:
    cat_filter = st.multiselect(
        "Filter by category",
        options=sorted(df["category"].unique()),
        default=[],
    )

display_df = df.copy()
if search:
    display_df = display_df[display_df["description"].str.contains(search, case=False, na=False)]
if cat_filter:
    display_df = display_df[display_df["category"].isin(cat_filter)]

display_df = display_df.sort_values("date", ascending=False)
cols_show = ["date", "description", "amount", "category", "subcategory", "balance"]
st.dataframe(
    display_df[cols_show].rename(columns={
        "date": "Date", "description": "Description",
        "amount": f"Amount ({currency})", "category": "Category",
        "subcategory": "Subcategory", "balance": "Balance",
    }),
    use_container_width=True,
    hide_index=True,
    height=350,
)

# ── CSV export ─────────────────────────────────────────────────────────────────
csv_bytes = df.to_csv(index=False).encode()
st.download_button(
    "⬇️ Download clean CSV",
    data=csv_bytes,
    file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)

# ── AI Chat ───────────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Ask Claude About Your Spending</p>', unsafe_allow_html=True)

if not st.session_state.api_key:
    st.info("💡 Enter your Anthropic API key in the sidebar to enable AI chat.")
else:
    # Build context summary for Claude
    cat_breakdown = (
        debits.groupby("category")["amount_abs"]
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )
    top_5_merchants = (
        debits.groupby("description")["amount_abs"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .to_dict()
    )
    recent_txns = df.sort_values("date", ascending=False).head(20)[
        ["date", "description", "amount", "category"]
    ].to_dict(orient="records")

    SYSTEM_PROMPT = f"""You are a personal finance advisor analyzing the user's bank statement.

Statement summary:
- Period: {df['date'].min().strftime('%B %d')} to {df['date'].max().strftime('%B %d, %Y')}
- Currency: {currency}
- Total spent: {spent:,.2f}
- Total received: {received:,.2f}
- Net: {net:+,.2f}
- Transactions: {len(df)}

Spending by category:
{json.dumps({k: round(v, 2) for k, v in cat_breakdown.items()}, indent=2)}

Top 5 merchants:
{json.dumps({k: round(v, 2) for k, v in top_5_merchants.items()}, indent=2)}

Recent transactions (last 20):
{json.dumps([{**r, 'date': str(r['date'])[:10]} for r in recent_txns], indent=2)}

Be concise, specific, and actionable. Use the actual numbers from the data. 
Format amounts with the currency code {currency}. Use bullet points for lists.
When giving suggestions, be practical and personalized to this person's actual spending patterns."""

    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="user-bubble">👤 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ai-bubble">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

    # Quick suggestion buttons
    if not st.session_state.messages:
        st.markdown("**Quick questions:**")
        q_cols = st.columns(3)
        quick_qs = [
            "Where am I overspending?",
            "How can I save more money?",
            "What are my biggest expenses?",
            "Analyze my food spending",
            "Any unusual transactions?",
            "Give me a monthly summary",
        ]
        for i, q in enumerate(quick_qs):
            with q_cols[i % 3]:
                if st.button(q, key=f"quick_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": q})
                    st.rerun()

    # Chat input
    user_input = st.chat_input("Ask anything about your spending...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.rerun()

    # Generate AI response
    if st.session_state.messages and (
        len(st.session_state.messages) == 0 or
        st.session_state.messages[-1]["role"] == "user"
    ):
        last = st.session_state.messages[-1] if st.session_state.messages else None
        if last and last["role"] == "user":
            with st.spinner("Claude is thinking..."):
                try:
                    client = Anthropic(api_key=st.session_state.api_key)
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1024,
                        system=SYSTEM_PROMPT,
                        messages=st.session_state.messages,
                    )
                    reply = response.content[0].text
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.rerun()
                except Exception as e:
                    st.error(f"API error: {e}")

    # Clear chat
    if st.session_state.messages:
        if st.button("🗑️ Clear chat"):
            st.session_state.messages = []
            st.rerun()
