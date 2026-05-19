"""
Personal Finance Manager — Phase 4
New: Monthly income input, smart 50/30/20 budget suggestions,
     savings tracker, income vs spending chart, monthly income prompt
"""

import json, tempfile, math, urllib.request
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from anthropic import Anthropic
from parser import parse_statement
from categorizer import tag_dataframe

st.set_page_config(page_title="Scotty Budget Management", page_icon="💰",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ──────────────────────────────────────────────────────────

   GLOBAL

────────────────────────────────────────────────────────── */

html, body, [class*="css"]{

    font-family:'DM Sans',sans-serif;

    background:#0b0b12;

    color:#e6e6f0;

}

/* Hide Streamlit top spacing */

.block-container{

    padding-top:1.5rem;

}

/* ──────────────────────────────────────────────────────────

   TOP HEADER / BRANDING

────────────────────────────────────────────────────────── */

.top-brand{

    display:flex;

    align-items:center;

    justify-content:space-between;

    background:linear-gradient(135deg,#121826,#1b1b2d);

    border:1px solid #2a2a3a;

    border-radius:24px;

    padding:1.5rem 1.8rem;

    margin-bottom:1.4rem;

    box-shadow:0 12px 35px rgba(0,0,0,.25);

}

.brand-left{

    display:flex;

    align-items:center;

    gap:1rem;

}

.brand-logo{

    width:64px;

    height:64px;

    border-radius:20px;

    background:linear-gradient(135deg,#7c6fff,#3b9eff);

    display:flex;

    align-items:center;

    justify-content:center;

    font-size:1.8rem;

    box-shadow:0 10px 25px rgba(124,111,255,.25);

}

.brand-title{

    font-size:2rem;

    font-weight:700;

    color:#ffffff;

    line-height:1.1;

}

.brand-sub{

    color:#8f9bb3;

    font-size:.95rem;

    margin-top:.35rem;

}

/* ──────────────────────────────────────────────────────────

   HERO IMAGE UPLOAD

────────────────────────────────────────────────────────── */

.hero-upload{

    background:#12121c;

    border:1px dashed #3b9eff;

    border-radius:20px;

    padding:1.2rem;

    margin-bottom:1.5rem;

}

/* ──────────────────────────────────────────────────────────

   METRIC CARDS

────────────────────────────────────────────────────────── */

.mc{

    background:#1a1a24;

    border:1px solid #2a2a3a;

    border-radius:18px;

    padding:1.4rem;

    text-align:center;

    transition:all .2s ease;

}

.mc:hover{

    transform:translateY(-3px);

    border-color:#3b3b50;

}

.mc .lb{

    font-size:.72rem;

    color:#888;

    text-transform:uppercase;

    letter-spacing:.08em;

    margin-bottom:.3rem;

}

.mc .vl{

    font-size:1.7rem;

    font-weight:600;

    font-family:'DM Mono',monospace;

}

.mc .sb{

    font-size:.72rem;

    color:#666;

    margin-top:.25rem;

}

/* ──────────────────────────────────────────────────────────

   SECTION HEADERS

────────────────────────────────────────────────────────── */

.sh{

    font-size:.72rem;

    font-weight:700;

    color:#666;

    text-transform:uppercase;

    letter-spacing:.12em;

    margin:2rem 0 1rem;

    padding-bottom:.5rem;

    border-bottom:1px solid #2a2a3a;

}

/* ──────────────────────────────────────────────────────────

   BUDGET CARDS

────────────────────────────────────────────────────────── */

.bw{

    background:#1a1a24;

    border:1px solid #2a2a3a;

    border-radius:14px;

    padding:1rem 1.2rem;

    margin:.5rem 0;

}

.br{

    display:flex;

    justify-content:space-between;

    font-size:.85rem;

    color:#ccc;

    margin-bottom:.45rem;

}

.tr{

    background:#2a2a3a;

    border-radius:6px;

    height:8px;

    overflow:hidden;

}

.fl{

    height:8px;

    border-radius:6px;

}

/* ──────────────────────────────────────────────────────────

   CHAT BUBBLES

────────────────────────────────────────────────────────── */

.ai-b{

    background:#1a1a24;

    border:1px solid #2a2a3a;

    border-left:3px solid #7c6fff;

    border-radius:14px;

    padding:1.1rem 1.4rem;

    margin:.7rem 0;

    font-size:.93rem;

    line-height:1.75;

    color:#d0d0e0;

}

.usr-b{

    background:#16202e;

    border:1px solid #1e3048;

    border-left:3px solid #3b9eff;

    border-radius:14px;

    padding:.95rem 1.4rem;

    margin:.7rem 0;

    font-size:.93rem;

    color:#b0c8e8;

}

/* ──────────────────────────────────────────────────────────

   SAVINGS CARDS

────────────────────────────────────────────────────────── */

.sv{

    background:#0e1f14;

    border:1px solid #1a3a24;

    border-radius:16px;

    padding:1.2rem;

    margin:.4rem 0;

}

.sv .am{

    font-size:1.4rem;

    font-weight:600;

    color:#69db7c;

    font-family:'DM Mono',monospace;

}

/* ──────────────────────────────────────────────────────────

   RECURRING CHARGES

────────────────────────────────────────────────────────── */

.rc{

    background:#1a1a24;

    border:1px solid #2a2a3a;

    border-radius:12px;

    padding:.8rem 1rem;

    margin:.4rem 0;

    display:flex;

    justify-content:space-between;

    align-items:center;

}

/* ──────────────────────────────────────────────────────────

   INCOME BOX

────────────────────────────────────────────────────────── */

.income-box{

    background:#0e1520;

    border:2px solid #1e3a50;

    border-radius:18px;

    padding:1.5rem;

    margin:1rem 0;

}

/* ──────────────────────────────────────────────────────────

   BUTTONS

────────────────────────────────────────────────────────── */

.stButton > button{

    background:linear-gradient(135deg,#7c6fff,#5a7dff);

    color:#fff;

    border:none;

    border-radius:12px;

    padding:.6rem 1.4rem;

    font-family:'DM Sans',sans-serif;

    font-weight:600;

    transition:all .2s ease;

}

.stButton > button:hover{

    transform:translateY(-2px);

    background:linear-gradient(135deg,#9b8fff,#7094ff);

    box-shadow:0 8px 20px rgba(124,111,255,.25);

}

/* ──────────────────────────────────────────────────────────

   SIDEBAR

────────────────────────────────────────────────────────── */

div[data-testid="stSidebar"]{

    background:#0d0d15;

    border-right:1px solid #1e1e2e;

}

div[data-testid="stSidebar"] *{

    color:#d8d8e5;

}

/* ──────────────────────────────────────────────────────────

   INPUTS

────────────────────────────────────────────────────────── */

.stTextInput input,

.stNumberInput input,

.stSelectbox div[data-baseweb="select"]{

    background:#161622 !important;

    border:1px solid #2a2a3a !important;

    border-radius:10px !important;

    color:#fff !important;

}

/* ──────────────────────────────────────────────────────────

   TABS

────────────────────────────────────────────────────────── */

button[data-baseweb="tab"]{

    background:#14141d;

    border-radius:10px;

    color:#aaa;

    margin-right:.3rem;

    padding:.55rem 1rem;

}

button[data-baseweb="tab"][aria-selected="true"]{

    background:#7c6fff !important;

    color:#fff !important;

}

/* ──────────────────────────────────────────────────────────

   DATAFRAMES

────────────────────────────────────────────────────────── */

[data-testid="stDataFrame"]{

    border:1px solid #2a2a3a;

    border-radius:14px;

    overflow:hidden;

}
</style>
""", unsafe_allow_html=True)

CAT_COLORS = {
    "Food & Drink":"#ff6b6b","Travel":"#4ecdc4","Shopping":"#ffe66d",
    "Health":"#a8e6cf","Subscriptions":"#c3a6ff","Entertainment":"#ffa07a",
    "Services":"#87ceeb","Income":"#69db7c","Transfer":"#b0b0b0","Other":"#555577",
}
# 50/30/20 rule allocation per category
NEEDS_CATS  = ["Food & Drink","Health","Services"]
WANTS_CATS  = ["Shopping","Entertainment","Subscriptions","Travel"]
SAVINGS_PCT = 0.20

DEFAULT_BUDGETS = {
    "Food & Drink":800,"Travel":500,"Shopping":400,"Health":200,
    "Subscriptions":50,"Entertainment":100,"Services":50,"Other":100,
}

# ── Supabase ──────────────────────────────────────────────────────────────────
def get_creds():
    try:
        u = st.secrets.get("SUPABASE_URL",""); k = st.secrets.get("SUPABASE_KEY","")
        if u and k: return u.rstrip("/"), k
    except: pass
    return None, None

def load_db():
    u,k = get_creds()
    if not u: return None
    try:
        req = urllib.request.Request(f"{u}/rest/v1/transactions?select=*&limit=5000",
            headers={"apikey":k,"Authorization":f"Bearer {k}"})
        data = json.loads(urllib.request.urlopen(req,timeout=10).read())
        if data:
            df = pd.DataFrame(data); df["date"] = pd.to_datetime(df["date"]); return df
    except: pass
    return None

def save_db(df):
    u,k = get_creds()
    if not u: return False
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"{u}/rest/v1/transactions?id=gte.0", method="DELETE",
            headers={"apikey":k,"Authorization":f"Bearer {k}","Content-Type":"application/json"}
        ), timeout=10)
    except: pass
    try:
        rec = df.copy(); rec["date"] = rec["date"].astype(str)
        for c in ["id","created_at"]:
            if c in rec.columns: rec = rec.drop(columns=[c])
        clean = [{kk:(None if isinstance(vv,float) and math.isnan(vv) else vv)
                  for kk,vv in r.items()} for r in rec.to_dict(orient="records")]
        for i in range(0,len(clean),100):
            urllib.request.urlopen(urllib.request.Request(
                f"{u}/rest/v1/transactions", data=json.dumps(clean[i:i+100]).encode(), method="POST",
                headers={"apikey":k,"Authorization":f"Bearer {k}",
                         "Content-Type":"application/json","Prefer":"return=minimal"}
            ), timeout=15)
        return True
    except Exception as e:
        st.sidebar.warning(f"DB error: {e}"); return False

def load_income_db():
    u,k = get_creds()
    if not u: return {}
    try:
        req = urllib.request.Request(f"{u}/rest/v1/income?select=*",
            headers={"apikey":k,"Authorization":f"Bearer {k}"})
        data = json.loads(urllib.request.urlopen(req,timeout=10).read())
        return {r["month"]:r["amount"] for r in data} if data else {}
    except: return {}

def save_income_db(month_str, amount):
    u,k = get_creds()
    if not u: return False
    try:
        # upsert
        body = json.dumps([{"month":month_str,"amount":amount}]).encode()
        urllib.request.urlopen(urllib.request.Request(
            f"{u}/rest/v1/income", data=body, method="POST",
            headers={"apikey":k,"Authorization":f"Bearer {k}",
                     "Content-Type":"application/json","Prefer":"resolution=merge-duplicates,return=minimal"}
        ), timeout=10)
        return True
    except: return False

# ── Session init ──────────────────────────────────────────────────────────────
for k,v in [("df",None),("messages",[]),("api_key",""),
            ("budgets",DEFAULT_BUDGETS.copy()),("db_loaded",False),
            ("income_by_month",{}),("show_income_prompt",False)]:
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state.db_loaded:
    db_df = load_db()
    if db_df is not None and len(db_df)>0: st.session_state.df = db_df
    st.session_state.income_by_month = load_income_db()
    st.session_state.db_loaded = True

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Finance Manager")
    st.markdown("---")
    api_in = st.text_input("Anthropic API Key", value=st.session_state.api_key,
                            type="password", placeholder="sk-ant-...")
    if api_in: st.session_state.api_key = api_in

    st.markdown("---")
    st.markdown("**Upload Statement**")
    uploaded = st.file_uploader("file", type=["csv","xlsx","xls","pdf"], label_visibility="collapsed")
    if uploaded:
        bank = st.selectbox("Bank",["auto","td_cibc","krung_thai","generic"],
            format_func=lambda x:{"auto":"🔍 Auto","td_cibc":"🍁 TD/CIBC",
                                   "krung_thai":"🇹🇭 Krung Thai","generic":"🌐 Generic"}[x])
        cur_in = st.text_input("Currency (optional)", placeholder="CAD / THB / USD")
        merge  = st.checkbox("Merge with existing data", value=True)

        if st.button("📊 Parse & Save", use_container_width=True):
            with st.spinner("Parsing..."):
                try:
                    sfx = "." + uploaded.name.split(".")[-1].lower()
                    with tempfile.NamedTemporaryFile(delete=False,suffix=sfx) as tmp:
                        tmp.write(uploaded.read()); tmp_path = tmp.name
                    new_df = parse_statement(tmp_path, bank=bank, currency=cur_in.strip() or None)
                    new_df = tag_dataframe(new_df)
                    if merge and st.session_state.df is not None:
                        combined = pd.concat([st.session_state.df,new_df],ignore_index=True)
                        combined = combined.drop_duplicates(subset=["date","description","amount"])
                        st.session_state.df = combined.sort_values("date").reset_index(drop=True)
                    else:
                        st.session_state.df = new_df
                    saved = save_db(st.session_state.df)
                    note  = "☁️ Synced to cloud" if saved else "💾 Local only"
                    st.session_state.messages = []
                    st.session_state.show_income_prompt = True
                    st.success(f"✅ {len(new_df)} transactions · {note}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")
    if st.session_state.df is not None:
        df0 = st.session_state.df
        st.markdown(f"**{len(df0)} transactions loaded**")
        st.markdown(f"📅 {df0['date'].min().strftime('%b %d')} – {df0['date'].max().strftime('%b %d, %Y')}")
        if st.button("🗑️ Clear all data", use_container_width=True):
            st.session_state.df = None; st.session_state.messages = []
            u,k = get_creds()
            if u:
                try:
                    urllib.request.urlopen(urllib.request.Request(
                        f"{u}/rest/v1/transactions?id=gte.0", method="DELETE",
                        headers={"apikey":k,"Authorization":f"Bearer {k}","Content-Type":"application/json"}
                    ), timeout=10)
                except: pass
            st.rerun()

    st.markdown("---")
    st.markdown("**Monthly Budgets**")
    for cat in DEFAULT_BUDGETS:
        st.session_state.budgets[cat] = st.number_input(
            cat, min_value=0, max_value=9999,
            value=st.session_state.budgets.get(cat,DEFAULT_BUDGETS[cat]),
            step=50, key=f"bgt_{cat}")

# ── No data guard ─────────────────────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown("""

    <div class="top-brand">

        <div class="brand-left">

            <div class="brand-logo">💰</div>

            <div>

                <div class="brand-title">Scotty Budget Management</div>

                <div class="brand-sub">Upload a bank statement to begin tracking your money beautifully.</div>

            </div>

        </div>

    </div>

    """, unsafe_allow_html=True)

    st.markdown("""

    <div class="income-box">

        <h3 style="color:#3b9eff;margin:0 0 .5rem">👈 Get Started</h3>

        <p style="color:#888;font-size:.95rem;margin:0">

            Upload your bank statement from the sidebar to view your dashboard,

            spending insights, budgets, savings tracker, and AI finance assistant.

        </p>

    </div>

    """, unsafe_allow_html=True)

    st.stop()

df  = st.session_state.df

cur = df["currency"].iloc[0]

bgt = st.session_state.budgets

# ── Top Header / Branding ─────────────────────────────────────────────────────

st.markdown("""

<div class="top-brand">

    <div class="brand-left">

        <div class="brand-logo">💰</div>

        <div>

            <div class="brand-title">Scotty Budget Management</div>

            <div class="brand-sub">Smart personal finance, budgeting, and savings tracking.</div>

        </div>

    </div>

</div>

""", unsafe_allow_html=True)

# ── Dashboard Image Upload ────────────────────────────────────────────────────

st.markdown("""

<div class="hero-upload">

    <div style="font-size:1rem;font-weight:600;color:#e6e6f0;margin-bottom:.25rem;">

        🖼️ Dashboard Cover Image

    </div>

    <div style="font-size:.85rem;color:#8f9bb3;margin-bottom:.8rem;">

        Upload a logo, banner, or personal finance image to customize your dashboard.

    </div>

</div>

""", unsafe_allow_html=True)

top_image = st.file_uploader(

    "Upload dashboard image",

    type=["png", "jpg", "jpeg"],

    key="dashboard_image_upload",

    label_visibility="collapsed"

)

if top_image:

    st.image(top_image, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Income prompt (pops up after upload) ──────────────────────────────────────

latest_month     = df["date"].max().replace(day=1)

latest_month_str = latest_month.strftime("%Y-%m")

latest_month_lbl = latest_month.strftime("%B %Y")

if st.session_state.show_income_prompt or \

   latest_month_str not in st.session_state.income_by_month:

    with st.container():

        st.markdown(f"""

        <div class="income-box">

            <h3 style="color:#3b9eff;margin:0 0 .5rem">

                💵 What was your income in {latest_month_lbl}?

            </h3>

            <p style="color:#888;font-size:.9rem;margin:0">

                Enter your total take-home pay for this month. This lets the app suggest

                smart budgets using the 50/30/20 rule and track your savings rate.

            </p>

        </div>

        """, unsafe_allow_html=True)

        ic1, ic2, ic3 = st.columns([2,1,1])

        with ic1:

            income_input = st.number_input(

                f"Monthly take-home income ({cur})",

                min_value=0.0,

                max_value=999999.0,

                value=0.0,

                step=100.0,

                key="income_input_field"

            )

        with ic2:

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("✅ Save income", use_container_width=True):

                if income_input > 0:

                    st.session_state.income_by_month[latest_month_str] = income_input

                    save_income_db(latest_month_str, income_input)

                    needs  = income_input * 0.50

                    wants  = income_input * 0.30

                    for cat in DEFAULT_BUDGETS:

                        if cat in NEEDS_CATS:

                            st.session_state.budgets[cat] = round(

                                needs / len(NEEDS_CATS) / 50

                            ) * 50

                        elif cat in WANTS_CATS:

                            st.session_state.budgets[cat] = round(

                                wants / len(WANTS_CATS) / 50

                            ) * 50

                    st.session_state.show_income_prompt = False

                    st.rerun()

        with ic3:

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("Skip for now", use_container_width=True):

                st.session_state.show_income_prompt = False

                st.rerun()

        st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5 = st.tabs(["📊 Dashboard","🎯 Budgets & Income","📅 Monthly","💡 Insights","🤖 Ask Claude"])

# ════════════ TAB 1 — DASHBOARD ════════════
with tab1:
    income_this_month = st.session_state.income_by_month.get(latest_month_str, 0)
    spent   = abs(df[df["amount"]<0]["amount"].sum())
    recv    = df[df["amount"]>0]["amount"].sum()
    net     = df["amount"].sum()
    n_tx    = len(df[df["amount"]<0])
    avg     = spent/n_tx if n_tx else 0
    savings = income_this_month - abs(df[
        (df["date"].dt.year==latest_month.year)&
        (df["date"].dt.month==latest_month.month)&
        (df["amount"]<0)]["amount"].sum()) if income_this_month else None

    cols = st.columns(5 if income_this_month else 4)
    for col,lbl,val,sub,clr in [
        (cols[0],"Total Spent",    f"{cur} {spent:,.2f}", f"{n_tx} transactions","#ff6b6b"),
        (cols[1],"Total Received", f"{cur} {recv:,.2f}",  "payments & credits",  "#69db7c"),
        (cols[2],"Net",            f"{'+' if net>=0 else ''}{cur} {net:,.2f}","this period","#69db7c" if net>=0 else "#ff6b6b"),
        (cols[3],"Avg Transaction",f"{cur} {avg:,.2f}",   "per purchase",        "#f0f0f0"),
    ]:
        col.markdown(f'<div class="mc"><div class="lb">{lbl}</div>'
                     f'<div class="vl" style="color:{clr}">{val}</div>'
                     f'<div class="sb">{sub}</div></div>', unsafe_allow_html=True)
    if income_this_month and savings is not None:
        sv_clr = "#69db7c" if savings>=0 else "#ff6b6b"
        sv_pct = savings/income_this_month*100 if income_this_month else 0
        cols[4].markdown(f'<div class="mc"><div class="lb">Saved This Month</div>'
                         f'<div class="vl" style="color:{sv_clr}">{cur} {savings:,.2f}</div>'
                         f'<div class="sb">{sv_pct:.1f}% of income</div></div>', unsafe_allow_html=True)

    # Income vs spending bar if income set
    if income_this_month:
        st.markdown('<p class="sh">Income vs Spending This Month</p>', unsafe_allow_html=True)
        month_spent = abs(df[
            (df["date"].dt.year==latest_month.year)&
            (df["date"].dt.month==latest_month.month)&
            (df["amount"]<0)]["amount"].sum())
        target_save = income_this_month * SAVINGS_PCT
        fig_iv = go.Figure()
        fig_iv.add_trace(go.Bar(name="Income",    x=["This Month"], y=[income_this_month], marker_color="#69db7c"))
        fig_iv.add_trace(go.Bar(name="Spent",     x=["This Month"], y=[month_spent],       marker_color="#ff6b6b"))
        fig_iv.add_trace(go.Bar(name="Saved",     x=["This Month"], y=[max(0,income_this_month-month_spent)], marker_color="#4ecdc4"))
        fig_iv.add_hline(y=target_save, line_dash="dot", line_color="#ffe66d",
                         annotation_text=f"20% savings goal ({cur} {target_save:,.0f})")
        fig_iv.update_layout(barmode="group", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font_color="#c0c0d0",
            margin=dict(t=30,b=10,l=10,r=10), height=260,
            legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fig_iv, use_container_width=True)

    st.markdown('<p class="sh">Spending Breakdown</p>', unsafe_allow_html=True)
    deb=df[df["amount"]<0].copy(); deb["abs"]=deb["amount"].abs()
    ct=deb.groupby("category")["abs"].sum().reset_index().sort_values("abs",ascending=False)
    clrs=[CAT_COLORS.get(c,"#555577") for c in ct["category"]]
    l,r=st.columns(2)
    with l:
        fig=go.Figure(go.Pie(labels=ct["category"],values=ct["abs"],marker_colors=clrs,hole=.55,
            textinfo="percent",hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=10,b=10,l=10,r=10),height=280)
        st.plotly_chart(fig,use_container_width=True)
    with r:
        fig2=go.Figure(go.Bar(x=ct["abs"],y=ct["category"],orientation="h",marker_color=clrs,
            text=[f"{cur} {v:,.0f}" for v in ct["abs"]],textposition="outside"))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=10,b=10,l=10,r=120),
            xaxis=dict(showgrid=False,visible=False),yaxis=dict(showgrid=False),height=280)
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown('<p class="sh">Daily Spending Trend</p>', unsafe_allow_html=True)
    dy=deb.groupby("date")["abs"].sum().reset_index()
    fig3=go.Figure(go.Scatter(x=dy["date"],y=dy["abs"],mode="lines+markers",
        line=dict(color="#7c6fff",width=2),marker=dict(size=5,color="#7c6fff"),
        fill="tozeroy",fillcolor="rgba(124,111,255,0.1)"))
    fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0d0",margin=dict(t=10,b=10,l=10,r=10),
        xaxis=dict(showgrid=False,color="#666"),yaxis=dict(showgrid=True,gridcolor="#1e1e2e",color="#666"),height=200)
    st.plotly_chart(fig3,use_container_width=True)

    st.markdown('<p class="sh">Top Merchants</p>', unsafe_allow_html=True)
    tm=deb.groupby("description")["abs"].sum().sort_values(ascending=False).head(10).reset_index()
    tm.columns=["Merchant",f"Total ({cur})"]; tm[f"Total ({cur})"]=tm[f"Total ({cur})"].map(lambda x:f"{x:,.2f}")
    st.dataframe(tm,use_container_width=True,hide_index=True)

    st.markdown('<p class="sh">All Transactions</p>', unsafe_allow_html=True)
    s1,s2=st.columns([2,1])
    with s1: srch=st.text_input("Search",placeholder="merchant name...")
    with s2: cf=st.multiselect("Category",sorted(df["category"].unique()))
    disp=df.sort_values("date",ascending=False)
    if srch: disp=disp[disp["description"].str.contains(srch,case=False,na=False)]
    if cf:   disp=disp[disp["category"].isin(cf)]
    st.dataframe(disp[["date","description","amount","category","subcategory","balance"]]
        .rename(columns={"date":"Date","description":"Description","amount":f"Amount ({cur})",
                         "category":"Category","subcategory":"Sub","balance":"Balance"}),
        use_container_width=True,hide_index=True,height=300)
    st.download_button("⬇️ Download CSV",df.to_csv(index=False).encode(),
        file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",mime="text/csv")

# ════════════ TAB 2 — BUDGETS & INCOME ════════════
with tab2:
    st.markdown("### 🎯 Budgets & Income")

    # Income section
    st.markdown('<p class="sh">Monthly Income</p>', unsafe_allow_html=True)
    all_months = sorted(set(
        df["date"].dt.to_period("M").astype(str).unique()
    ))

    for m in reversed(all_months):
        m_lbl   = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
        m_income= st.session_state.income_by_month.get(m, 0)
        mask_m  = (df["date"].dt.year==int(m[:4]))&(df["date"].dt.month==int(m[5:]))
        m_spent = abs(df[mask_m&(df["amount"]<0)]["amount"].sum())
        m_saved = m_income - m_spent if m_income else None
        sv_rate = m_saved/m_income*100 if m_income and m_saved is not None else None

        with st.expander(f"**{m_lbl}**" + (f"  ·  income {cur} {m_income:,.0f}  ·  spent {cur} {m_spent:,.0f}" if m_income else f"  ·  spent {cur} {m_spent:,.0f}  ·  ⚠️ No income entered"), expanded=(m==latest_month_str)):
            ic1,ic2,ic3=st.columns([2,1,1])
            with ic1:
                new_inc=st.number_input(f"Income ({cur})",min_value=0.0,max_value=999999.0,
                    value=float(m_income),step=100.0,key=f"inc_{m}")
            with ic2:
                st.markdown("<br>",unsafe_allow_html=True)
                if st.button("Save",key=f"saveinc_{m}",use_container_width=True):
                    st.session_state.income_by_month[m]=new_inc
                    save_income_db(m,new_inc)
                    # Auto-update budgets using 50/30/20
                    if new_inc>0:
                        needs=new_inc*0.50; wants=new_inc*0.30
                        for cat in DEFAULT_BUDGETS:
                            if cat in NEEDS_CATS:
                                st.session_state.budgets[cat]=round(needs/len(NEEDS_CATS)/50)*50
                            elif cat in WANTS_CATS:
                                st.session_state.budgets[cat]=round(wants/len(WANTS_CATS)/50)*50
                    st.rerun()
            with ic3:
                if m_income and sv_rate is not None:
                    sv_clr="#69db7c" if m_saved>=0 else "#ff6b6b"
                    st.markdown(f"<br><span style='color:{sv_clr};font-weight:600'>"
                                f"Saved: {cur} {m_saved:,.0f} ({sv_rate:.1f}%)</span>",unsafe_allow_html=True)

            if m_income>0:
                target_save=m_income*SAVINGS_PCT
                st.markdown(f"""
                <div style='font-size:.82rem;color:#888;margin-top:.5rem'>
                50/30/20 targets &nbsp;·&nbsp;
                Needs: <b style='color:#ccc'>{cur} {m_income*.5:,.0f}</b> &nbsp;·&nbsp;
                Wants: <b style='color:#ccc'>{cur} {m_income*.3:,.0f}</b> &nbsp;·&nbsp;
                Save: <b style='color:#69db7c'>{cur} {target_save:,.0f}</b>
                </div>""",unsafe_allow_html=True)

    # Budget bars
    st.markdown('<p class="sh">Category Budgets (current month)</p>', unsafe_allow_html=True)
    mask_cur=(df["date"].dt.year==latest_month.year)&(df["date"].dt.month==latest_month.month)
    mdeb=df[mask_cur&(df["amount"]<0)].copy(); mdeb["abs"]=mdeb["amount"].abs()
    cs=mdeb.groupby("category")["abs"].sum().to_dict()
    tot_bgt=sum(bgt.values()); tot_sp=sum(cs.values()); rem=tot_bgt-tot_sp

    b1,b2,b3=st.columns(3)
    b1.markdown(f'<div class="mc"><div class="lb">Total Budget</div><div class="vl">{cur} {tot_bgt:,.0f}</div></div>',unsafe_allow_html=True)
    b2.markdown(f'<div class="mc"><div class="lb">Spent</div><div class="vl" style="color:#ff6b6b">{cur} {tot_sp:,.2f}</div></div>',unsafe_allow_html=True)
    rc2="#69db7c" if rem>=0 else "#ff6b6b"
    b3.markdown(f'<div class="mc"><div class="lb">Remaining</div><div class="vl" style="color:{rc2}">{cur} {abs(rem):,.2f} {"left" if rem>=0 else "OVER"}</div></div>',unsafe_allow_html=True)

    for cat,budget in bgt.items():
        if budget==0: continue
        sp=cs.get(cat,0); pct=min(sp/budget*100,100) if budget else 0
        over=sp>budget; bc="#ff6b6b" if over else ("#ffe66d" if pct>75 else "#69db7c")
        status=f"⚠️ Over by {cur} {sp-budget:,.2f}" if over else f"{cur} {budget-sp:,.2f} left"
        st.markdown(f"""<div class="bw"><div class="br"><span>{cat}</span>
            <span style="color:#888">{cur} {sp:,.2f} / {cur} {budget:,.0f} &nbsp;·&nbsp;
            <span style="color:{'#ff6b6b' if over else '#69db7c'}">{status}</span></span></div>
            <div class="tr"><div class="fl" style="width:{pct}%;background:{bc}"></div></div>
        </div>""",unsafe_allow_html=True)

# ════════════ TAB 3 — MONTHLY ════════════
with tab3:
    st.markdown("### 📅 Month-over-Month")
    df["month"]=df["date"].dt.to_period("M")
    months=sorted(df["month"].unique())
    if len(months)<2:
        st.info("Upload statements from at least 2 months to see comparison.")
    else:
        dm=df[df["amount"]<0].copy(); dm["abs"]=dm["amount"].abs()
        mo=dm.groupby(["month","category"])["abs"].sum().reset_index()
        mo["month_str"]=mo["month"].astype(str)
        fig_m=px.bar(mo,x="month_str",y="abs",color="category",color_discrete_map=CAT_COLORS,
            barmode="stack",labels={"abs":f"Amount ({cur})","month_str":"Month"},template="plotly_dark")
        fig_m.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=20,b=10,l=10,r=10),height=360)
        st.plotly_chart(fig_m,use_container_width=True)

        # income vs spending by month
        inc_data = st.session_state.income_by_month
        if inc_data:
            st.markdown('<p class="sh">Income vs Spending by Month</p>', unsafe_allow_html=True)
            mts=dm.groupby("month")["abs"].sum().reset_index()
            mts["month_str"]=mts["month"].astype(str)
            mts["income"]=mts["month_str"].map(inc_data).fillna(0)
            mts["saved"]=mts["income"]-mts["abs"]
            fig_iv2=go.Figure()
            fig_iv2.add_trace(go.Bar(name="Income",x=mts["month_str"],y=mts["income"],marker_color="#69db7c"))
            fig_iv2.add_trace(go.Bar(name="Spent", x=mts["month_str"],y=mts["abs"],   marker_color="#ff6b6b"))
            fig_iv2.update_layout(barmode="group",paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",font_color="#c0c0d0",
                margin=dict(t=20,b=10,l=10,r=10),height=280)
            st.plotly_chart(fig_iv2,use_container_width=True)

# ════════════ TAB 4 — INSIGHTS ════════════
with tab4:
    st.markdown("### 💡 Smart Insights")
    di=df[df["amount"]<0].copy(); di["abs"]=di["amount"].abs()

    st.markdown('<p class="sh">Savings Opportunities</p>', unsafe_allow_html=True)
    coffee=di[di["subcategory"]=="Coffee"]["abs"].sum()
    delivery=di[di["subcategory"]=="Delivery"]["abs"].sum()
    subs=di[di["category"]=="Subscriptions"]["abs"].sum()
    savings_ops=[]
    if coffee>50:    savings_ops.append(("☕ Coffee",coffee,coffee*.5,"Cut by half"))
    if delivery>30:  savings_ops.append(("🛵 Delivery",delivery,delivery*.6,"Cook more"))
    if subs>20:      savings_ops.append(("📱 Subscriptions",subs,subs*.3,"Cancel unused"))
    if savings_ops:
        sc=st.columns(len(savings_ops))
        for i,(lbl,tot,sv,msg) in enumerate(savings_ops):
            sc[i].markdown(f'<div class="sv"><div style="font-size:.8rem;color:#888">{lbl}</div>'
                           f'<div class="am">{cur} {sv:,.2f}/mo</div>'
                           f'<div style="font-size:.78rem;color:#4a8a5a">{msg}</div>'
                           f'<div style="font-size:.72rem;color:#666">Current: {cur} {tot:,.2f}</div></div>',
                           unsafe_allow_html=True)
    else:
        st.success("No major savings opportunities — great habits!")

    st.markdown('<p class="sh">Recurring Charges</p>', unsafe_allow_html=True)
    rc_df=di.groupby("description").agg(count=("abs","count"),total=("abs","sum"),avg=("abs","mean")).reset_index()
    rc_df=rc_df[rc_df["count"]>=2].sort_values("total",ascending=False)
    for _,row in rc_df.head(8).iterrows():
        st.markdown(f'<div class="rc"><span style="color:#d0d0e0">{row["description"]}</span>'
                    f'<span style="color:#888;font-size:.82rem">{int(row["count"])}× · '
                    f'avg {cur} {row["avg"]:,.2f} · total {cur} {row["total"]:,.2f}</span></div>',
                    unsafe_allow_html=True)

    st.markdown('<p class="sh">Largest Transactions</p>', unsafe_allow_html=True)
    big=di.nlargest(5,"abs")[["date","description","abs","category"]]
    big.columns=["Date","Description",f"Amount ({cur})","Category"]
    big[f"Amount ({cur})"]=big[f"Amount ({cur})"].map(lambda x:f"{x:,.2f}")
    st.dataframe(big,use_container_width=True,hide_index=True)

    st.markdown('<p class="sh">Spending by Day of Week</p>', unsafe_allow_html=True)
    di["dow"]=di["date"].dt.day_name()
    day_order=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow=di.groupby("dow")["abs"].sum().reindex(day_order).fillna(0).reset_index()
    fig_dow=go.Figure(go.Bar(x=dow["dow"],y=dow["abs"],
        marker_color=["#ff6b6b" if d in ["Saturday","Sunday"] else "#7c6fff" for d in dow["dow"]],
        text=[f"{cur} {v:,.0f}" for v in dow["abs"]],textposition="outside"))
    fig_dow.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0d0",margin=dict(t=30,b=10,l=10,r=10),
        yaxis=dict(showgrid=True,gridcolor="#1e1e2e"),height=260)
    st.plotly_chart(fig_dow,use_container_width=True)

# ════════════ TAB 5 — ASK CLAUDE ════════════
with tab5:
    st.markdown("### 🤖 Ask Claude About Your Money")
    if not st.session_state.api_key:
        st.info("💡 Enter your Anthropic API key in the sidebar.")
        st.stop()

    dai=df[df["amount"]<0].copy(); dai["abs"]=dai["amount"].abs()
    income_ctx = {m: st.session_state.income_by_month.get(m,0) for m in
                  df["date"].dt.to_period("M").astype(str).unique()}
    cb=dai.groupby("category")["abs"].sum().sort_values(ascending=False).to_dict()
    tm2=dai.groupby("description")["abs"].sum().sort_values(ascending=False).head(10).to_dict()
    rec=df.sort_values("date",ascending=False).head(30)[["date","description","amount","category"]]\
          .to_dict(orient="records")

    SYS=f"""You are a sharp personal finance advisor. Real bank data below.
Period: {df['date'].min().strftime('%B %d')} – {df['date'].max().strftime('%B %d, %Y')}
Currency: {cur} | Spent: {dai['abs'].sum():,.2f} | Net: {df['amount'].sum():+,.2f}
Income by month: {json.dumps(income_ctx)}
Spending by category: {json.dumps({k:round(v,2) for k,v in cb.items()})}
Top merchants: {json.dumps({k:round(v,2) for k,v in tm2.items()})}
Monthly budgets: {json.dumps(bgt)}
Recent 30 transactions: {json.dumps([{{**r,'date':str(r['date'])[:10]}} for r in rec])}
Be specific, reference actual numbers, use bullets. Calculate savings rate when income known."""

    for msg in st.session_state.messages:
        cls="usr-b" if msg["role"]=="user" else "ai-b"
        icon="👤" if msg["role"]=="user" else "🤖"
        st.markdown(f'<div class="{cls}">{icon} {msg["content"]}</div>',unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        qs=["What is my savings rate?","Am I on budget this month?",
            "Where am I overspending?","How to reach 20% savings?",
            "Analyze my food spending","Any subscriptions to cancel?",
            "Full financial summary","What should I cut first?"]
        cols=st.columns(4)
        for i,q in enumerate(qs):
            if cols[i%4].button(q,key=f"q{i}",use_container_width=True):
                st.session_state.messages.append({"role":"user","content":q}); st.rerun()

    user_in=st.chat_input("Ask anything about your finances...")
    if user_in:
        st.session_state.messages.append({"role":"user","content":user_in}); st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"]=="user":
        with st.spinner("Claude is thinking..."):
            try:
                client=Anthropic(api_key=st.session_state.api_key)
                resp=client.messages.create(model="claude-sonnet-4-20250514",max_tokens=1024,
                    system=SYS,messages=st.session_state.messages)
                st.session_state.messages.append({"role":"assistant","content":resp.content[0].text})
                st.rerun()
            except Exception as e:
                st.error(f"API error: {e}")

    if st.session_state.messages:
        if st.button("🗑️ Clear chat"): st.session_state.messages=[]; st.rerun()
