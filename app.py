"""
Personal Finance Manager — Phase 3
New in this version:
  - Supabase cloud database (data persists across all devices)
  - Budget goals per category
  - Month-over-month comparison
  - Savings opportunities tracker
  - Recurring charges detector
  - Weekday vs weekend analysis
  - Smarter Claude AI with budget context
"""

import os
import io
import json
import tempfile
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from anthropic import Anthropic

from parser import parse_statement
from categorizer import tag_dataframe

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Finance Manager", page_icon="💰",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.metric-card{background:#1a1a24;border:1px solid #2a2a3a;border-radius:16px;padding:1.4rem;text-align:center;}
.metric-card .label{font-size:.72rem;color:#888;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem;}
.metric-card .value{font-size:1.7rem;font-weight:600;color:#f0f0f0;font-family:'DM Mono',monospace;}
.metric-card .sub{font-size:.72rem;color:#666;margin-top:.25rem;}
.sh{font-size:.7rem;font-weight:600;color:#666;text-transform:uppercase;letter-spacing:.12em;
    margin:2rem 0 1rem;padding-bottom:.5rem;border-bottom:1px solid #2a2a3a;}
.budget-wrap{background:#1a1a24;border:1px solid #2a2a3a;border-radius:12px;padding:1rem 1.2rem;margin:.4rem 0;}
.budget-row{display:flex;justify-content:space-between;font-size:.85rem;color:#ccc;margin-bottom:.4rem;}
.track{background:#2a2a3a;border-radius:6px;height:8px;overflow:hidden;}
.fill{height:8px;border-radius:6px;}
.ai-b{background:#1a1a24;border:1px solid #2a2a3a;border-left:3px solid #7c6fff;
      border-radius:12px;padding:1.1rem 1.4rem;margin:.6rem 0;font-size:.93rem;line-height:1.75;color:#d0d0e0;}
.usr-b{background:#16202e;border:1px solid #1e3048;border-left:3px solid #3b9eff;
       border-radius:12px;padding:.9rem 1.4rem;margin:.6rem 0;font-size:.93rem;color:#b0c8e8;}
.save-card{background:#0e1f14;border:1px solid #1a3a24;border-radius:14px;padding:1.2rem;margin:.4rem 0;}
.save-card .amt{font-size:1.4rem;font-weight:600;color:#69db7c;font-family:'DM Mono',monospace;}
.rec{background:#1a1a24;border:1px solid #2a2a3a;border-radius:10px;
     padding:.75rem 1rem;margin:.3rem 0;display:flex;justify-content:space-between;align-items:center;}
.stButton>button{background:#7c6fff;color:#fff;border:none;border-radius:10px;
                 padding:.55rem 1.4rem;font-family:'DM Sans',sans-serif;font-weight:500;}
.stButton>button:hover{background:#9b8fff;transform:translateY(-1px);}
div[data-testid="stSidebar"]{background:#0d0d15;border-right:1px solid #1e1e2e;}
</style>
""", unsafe_allow_html=True)

CAT_COLORS = {
    "Food & Drink":"#ff6b6b","Travel":"#4ecdc4","Shopping":"#ffe66d",
    "Health":"#a8e6cf","Subscriptions":"#c3a6ff","Entertainment":"#ffa07a",
    "Services":"#87ceeb","Income":"#69db7c","Transfer":"#b0b0b0","Other":"#555577",
}
DEFAULT_BUDGETS = {
    "Food & Drink":800,"Travel":500,"Shopping":400,"Health":200,
    "Subscriptions":50,"Entertainment":100,"Services":50,"Other":100,
}

# ── Supabase helpers ──────────────────────────────────────────────────────────
def get_sb():
    url = st.secrets.get("SUPABASE_URL","")
    key = st.secrets.get("SUPABASE_KEY","")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None

def load_db():
    sb = get_sb()
    if not sb: return None
    try:
        res = sb.table("transactions").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df["date"] = pd.to_datetime(df["date"])
            return df
    except Exception:
        pass
    return None

def save_db(df):
    sb = get_sb()
    if not sb: return False
    try:
        sb.table("transactions").delete().neq("id",0).execute()
        rec = df.copy()
        rec["date"] = rec["date"].astype(str)
        for c in ["id","created_at"]:
            if c in rec.columns: rec = rec.drop(columns=[c])
        sb.table("transactions").insert(rec.to_dict(orient="records")).execute()
        return True
    except Exception as e:
        return False

# ── Session init ──────────────────────────────────────────────────────────────
for k,v in [("df",None),("messages",[]),("api_key",""),
            ("budgets",DEFAULT_BUDGETS.copy()),("db_loaded",False)]:
    if k not in st.session_state: st.session_state[k] = v

if not st.session_state.db_loaded:
    db_df = load_db()
    if db_df is not None and len(db_df) > 0:
        st.session_state.df = db_df
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
    uploaded = st.file_uploader("file", type=["csv","xlsx","xls","pdf"],
                                 label_visibility="collapsed")
    if uploaded:
        bank = st.selectbox("Bank", ["auto","td_cibc","krung_thai","generic"],
            format_func=lambda x:{"auto":"🔍 Auto-detect","td_cibc":"🍁 TD/CIBC",
                                   "krung_thai":"🇹🇭 Krung Thai","generic":"🌐 Generic"}[x])
        cur  = st.text_input("Currency (optional)", placeholder="CAD / THB / USD")
        merge= st.checkbox("Merge with existing data", value=True)

        if st.button("📊 Parse & Save", use_container_width=True):
            with st.spinner("Parsing..."):
                try:
                    sfx = "." + uploaded.name.split(".")[-1].lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=sfx) as tmp:
                        tmp.write(uploaded.read()); tmp_path = tmp.name
                    new_df = parse_statement(tmp_path, bank=bank, currency=cur.strip() or None)
                    new_df = tag_dataframe(new_df)
                    if merge and st.session_state.df is not None:
                        combined = pd.concat([st.session_state.df, new_df], ignore_index=True)
                        combined = combined.drop_duplicates(subset=["date","description","amount"])
                        st.session_state.df = combined.sort_values("date").reset_index(drop=True)
                    else:
                        st.session_state.df = new_df
                    saved = save_db(st.session_state.df)
                    note  = "☁️ Synced to cloud" if saved else "💾 Local only (add Supabase for cloud sync)"
                    st.session_state.messages = []
                    st.success(f"✅ {len(new_df)} transactions · {note}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("---")
    if st.session_state.df is not None:
        df = st.session_state.df
        st.markdown(f"**{len(df)} transactions loaded**")
        st.markdown(f"📅 {df['date'].min().strftime('%b %d')} – {df['date'].max().strftime('%b %d, %Y')}")
        if st.button("🗑️ Clear all data", use_container_width=True):
            st.session_state.df = None; st.session_state.messages = []
            sb = get_sb()
            if sb:
                try: sb.table("transactions").delete().neq("id",0).execute()
                except: pass
            st.rerun()

    st.markdown("---")
    st.markdown("**Monthly Budgets**")
    for cat in DEFAULT_BUDGETS:
        st.session_state.budgets[cat] = st.number_input(
            cat, min_value=0, max_value=9999,
            value=st.session_state.budgets.get(cat, DEFAULT_BUDGETS[cat]),
            step=50, key=f"bgt_{cat}")

# ── No data guard ─────────────────────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown("# 💰 Personal Finance Manager")
    st.info("👈 Upload a bank statement in the sidebar to get started.")
    st.markdown("---")
    st.markdown("### ☁️ Want your data on every device?")
    st.markdown("""
Follow these steps once to enable cloud sync (free):

**1.** Go to [supabase.com](https://supabase.com) → create a free account  
**2.** Create a new project → **Table Editor** → New table named `transactions`  
&nbsp;&nbsp;&nbsp;&nbsp;Add columns: `date` (text), `description` (text), `amount` (float8),  
&nbsp;&nbsp;&nbsp;&nbsp;`debit` (float8), `credit` (float8), `balance` (float8),  
&nbsp;&nbsp;&nbsp;&nbsp;`currency` (text), `bank` (text), `source_file` (text),  
&nbsp;&nbsp;&nbsp;&nbsp;`category` (text), `subcategory` (text)  
**3.** Go to **Settings → API** → copy your Project URL and anon public key  
**4.** In Streamlit Cloud → your app → **Settings → Secrets** → paste:
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
```
**5.** Redeploy — data now syncs across phone, tablet, and computer automatically ✅
    """)
    st.stop()

df  = st.session_state.df
cur = df["currency"].iloc[0]
bgt = st.session_state.budgets

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5 = st.tabs(["📊 Dashboard","🎯 Budgets","📅 Monthly","💡 Insights","🤖 Ask Claude"])

# ════════════════════════ TAB 1 — DASHBOARD ════════════════════════
with tab1:
    spent = abs(df[df["amount"]<0]["amount"].sum())
    recv  = df[df["amount"]>0]["amount"].sum()
    net   = df["amount"].sum()
    n_tx  = len(df[df["amount"]<0])
    avg   = spent/n_tx if n_tx else 0

    c1,c2,c3,c4 = st.columns(4)
    for col,lbl,val,sub,clr in [
        (c1,"Total Spent",    f"{cur} {spent:,.2f}", f"{n_tx} transactions","#ff6b6b"),
        (c2,"Total Received", f"{cur} {recv:,.2f}",  "payments & credits",  "#69db7c"),
        (c3,"Net Balance",    f"{'+' if net>=0 else ''}{cur} {net:,.2f}","income minus spending","#69db7c" if net>=0 else "#ff6b6b"),
        (c4,"Avg Transaction",f"{cur} {avg:,.2f}",   "per purchase",        "#f0f0f0"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="label">{lbl}</div>'
                     f'<div class="value" style="color:{clr}">{val}</div>'
                     f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)

    st.markdown('<p class="sh">Spending Breakdown</p>', unsafe_allow_html=True)
    deb = df[df["amount"]<0].copy(); deb["abs"] = deb["amount"].abs()
    ct  = deb.groupby("category")["abs"].sum().reset_index().sort_values("abs",ascending=False)
    clrs= [CAT_COLORS.get(c,"#555577") for c in ct["category"]]

    l,r = st.columns(2)
    with l:
        fig=go.Figure(go.Pie(labels=ct["category"],values=ct["abs"],marker_colors=clrs,hole=.55,
            textinfo="percent",hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=10,b=10,l=10,r=10),height=300)
        st.plotly_chart(fig,use_container_width=True)
    with r:
        fig2=go.Figure(go.Bar(x=ct["abs"],y=ct["category"],orientation="h",marker_color=clrs,
            text=[f"{cur} {v:,.0f}" for v in ct["abs"]],textposition="outside"))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=10,b=10,l=10,r=120),
            xaxis=dict(showgrid=False,visible=False),yaxis=dict(showgrid=False),height=300)
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown('<p class="sh">Daily Spending Trend</p>', unsafe_allow_html=True)
    dy=deb.groupby("date")["abs"].sum().reset_index()
    fig3=go.Figure(go.Scatter(x=dy["date"],y=dy["abs"],mode="lines+markers",
        line=dict(color="#7c6fff",width=2),marker=dict(size=5,color="#7c6fff"),
        fill="tozeroy",fillcolor="rgba(124,111,255,0.1)",
        hovertemplate="<b>%{x|%b %d}</b><br>%{y:,.2f}<extra></extra>"))
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
        use_container_width=True,hide_index=True,height=320)
    st.download_button("⬇️ Download CSV",df.to_csv(index=False).encode(),
        file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",mime="text/csv")

# ════════════════════════ TAB 2 — BUDGETS ════════════════════════
with tab2:
    st.markdown("### 🎯 Budget Tracker")
    latest = df["date"].max().replace(day=1)
    mask   = (df["date"].dt.year==latest.year)&(df["date"].dt.month==latest.month)
    mdeb   = df[mask&(df["amount"]<0)].copy(); mdeb["abs"]=mdeb["amount"].abs()
    cs     = mdeb.groupby("category")["abs"].sum().to_dict()

    tot_bgt = sum(bgt.values()); tot_sp = sum(cs.values()); rem = tot_bgt-tot_sp

    b1,b2,b3=st.columns(3)
    b1.markdown(f'<div class="metric-card"><div class="label">Monthly Budget</div>'
                f'<div class="value">{cur} {tot_bgt:,.0f}</div></div>',unsafe_allow_html=True)
    b2.markdown(f'<div class="metric-card"><div class="label">Spent This Month</div>'
                f'<div class="value" style="color:#ff6b6b">{cur} {tot_sp:,.2f}</div>'
                f'<div class="sub">{latest.strftime("%B %Y")}</div></div>',unsafe_allow_html=True)
    rc="#69db7c" if rem>=0 else "#ff6b6b"
    b3.markdown(f'<div class="metric-card"><div class="label">Remaining</div>'
                f'<div class="value" style="color:{rc}">{cur} {abs(rem):,.2f} '
                f'{"left" if rem>=0 else "OVER"}</div></div>',unsafe_allow_html=True)

    st.markdown('<p class="sh">Category Budgets</p>', unsafe_allow_html=True)
    for cat,budget in bgt.items():
        if budget==0: continue
        sp=cs.get(cat,0); pct=min(sp/budget*100,100) if budget else 0
        over=sp>budget
        bc="#ff6b6b" if over else ("#ffe66d" if pct>75 else "#69db7c")
        status=f"⚠️ Over by {cur} {sp-budget:,.2f}" if over else f"{cur} {budget-sp:,.2f} left"
        st.markdown(f"""<div class="budget-wrap">
            <div class="budget-row"><span>{cat}</span>
            <span style="color:#888">{cur} {sp:,.2f} / {cur} {budget:,.0f} &nbsp;·&nbsp;
            <span style="color:{'#ff6b6b' if over else '#69db7c'}">{status}</span></span></div>
            <div class="track"><div class="fill" style="width:{pct}%;background:{bc}"></div></div>
        </div>""",unsafe_allow_html=True)

# ════════════════════════ TAB 3 — MONTHLY ════════════════════════
with tab3:
    st.markdown("### 📅 Month-over-Month Comparison")
    df["month"]=df["date"].dt.to_period("M")
    months=sorted(df["month"].unique())
    if len(months)<2:
        st.info("Upload statements from at least 2 months to see comparison.")
    else:
        dm=df[df["amount"]<0].copy(); dm["abs"]=dm["amount"].abs()
        mo=dm.groupby(["month","category"])["abs"].sum().reset_index()
        mo["month_str"]=mo["month"].astype(str)
        fig_m=px.bar(mo,x="month_str",y="abs",color="category",color_discrete_map=CAT_COLORS,
            barmode="stack",labels={"abs":f"Amount ({cur})","month_str":"Month","category":"Category"},
            template="plotly_dark")
        fig_m.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c0c0d0",margin=dict(t=20,b=10,l=10,r=10),height=380)
        st.plotly_chart(fig_m,use_container_width=True)

        mt=dm.groupby("month")["abs"].sum().reset_index()
        mt["Month"]=mt["month"].astype(str)
        mt[f"Total Spent ({cur})"]=mt["abs"].map(lambda x:f"{x:,.2f}")
        st.dataframe(mt[["Month",f"Total Spent ({cur})"]],use_container_width=True,hide_index=True)

# ════════════════════════ TAB 4 — INSIGHTS ════════════════════════
with tab4:
    st.markdown("### 💡 Smart Insights")
    di=df[df["amount"]<0].copy(); di["abs"]=di["amount"].abs()

    # Savings opportunities
    st.markdown('<p class="sh">Savings Opportunities</p>', unsafe_allow_html=True)
    coffee  = di[di["subcategory"]=="Coffee"]["abs"].sum()
    delivery= di[di["subcategory"]=="Delivery"]["abs"].sum()
    subs    = di[di["category"]=="Subscriptions"]["abs"].sum()
    savings=[]
    if coffee>50:   savings.append(("☕ Coffee",coffee,coffee*.5,"Cut by half and save"))
    if delivery>30: savings.append(("🛵 Food delivery",delivery,delivery*.6,"Cook more, save"))
    if subs>20:     savings.append(("📱 Subscriptions",subs,subs*.3,"Cancel unused ones"))

    if savings:
        sc=st.columns(len(savings))
        for i,(lbl,tot,sv,msg) in enumerate(savings):
            sc[i].markdown(f"""<div class="save-card">
                <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">{lbl}</div>
                <div class="amt">{cur} {sv:,.2f}/mo</div>
                <div style="font-size:.78rem;color:#4a8a5a;margin-top:.3rem">{msg}</div>
                <div style="font-size:.72rem;color:#666;margin-top:.2rem">Current: {cur} {tot:,.2f}</div>
            </div>""",unsafe_allow_html=True)
    else:
        st.success("No major savings opportunities detected — great spending habits!")

    # Recurring charges
    st.markdown('<p class="sh">Recurring Charges</p>', unsafe_allow_html=True)
    rc_df=di.groupby("description").agg(count=("abs","count"),total=("abs","sum"),avg=("abs","mean")).reset_index()
    rc_df=rc_df[rc_df["count"]>=2].sort_values("total",ascending=False)
    if not rc_df.empty:
        for _,row in rc_df.head(8).iterrows():
            st.markdown(f"""<div class="rec">
                <span style="color:#d0d0e0">{row['description']}</span>
                <span style="color:#888;font-size:.82rem">
                {int(row['count'])}× · avg {cur} {row['avg']:,.2f} · total {cur} {row['total']:,.2f}</span>
            </div>""",unsafe_allow_html=True)
    else:
        st.info("No recurring charges detected yet.")

    # Biggest transactions
    st.markdown('<p class="sh">Largest Single Transactions</p>', unsafe_allow_html=True)
    big=di.nlargest(5,"abs")[["date","description","abs","category"]]
    big.columns=["Date","Description",f"Amount ({cur})","Category"]
    big[f"Amount ({cur})"]=big[f"Amount ({cur})"].map(lambda x:f"{x:,.2f}")
    st.dataframe(big,use_container_width=True,hide_index=True)

    # Weekday vs weekend
    st.markdown('<p class="sh">Weekday vs Weekend Spending</p>', unsafe_allow_html=True)
    di["is_weekend"]=di["date"].dt.dayofweek>=5
    wk=di.groupby("is_weekend")["abs"].agg(["sum","mean","count"]).reset_index()
    wk["label"]=wk["is_weekend"].map({True:"Weekend",False:"Weekday"})
    fig_wk=go.Figure(go.Bar(x=wk["label"],y=wk["sum"],marker_color=["#ff6b6b","#4ecdc4"],
        text=[f"{cur} {v:,.0f}" for v in wk["sum"]],textposition="outside"))
    fig_wk.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c0c0d0",margin=dict(t=30,b=10,l=10,r=10),
        yaxis=dict(showgrid=True,gridcolor="#1e1e2e"),height=260)
    st.plotly_chart(fig_wk,use_container_width=True)

    # Day of week heatmap
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

# ════════════════════════ TAB 5 — ASK CLAUDE ════════════════════════
with tab5:
    st.markdown("### 🤖 Ask Claude About Your Money")
    if not st.session_state.api_key:
        st.info("💡 Enter your Anthropic API key in the sidebar to enable AI chat.")
        st.stop()

    dai=df[df["amount"]<0].copy(); dai["abs"]=dai["amount"].abs()
    sp2=dai["abs"].sum(); rc2=df[df["amount"]>0]["amount"].sum(); nt2=df["amount"].sum()
    cb =dai.groupby("category")["abs"].sum().sort_values(ascending=False).to_dict()
    tm2=dai.groupby("description")["abs"].sum().sort_values(ascending=False).head(10).to_dict()
    rec=df.sort_values("date",ascending=False).head(30)[["date","description","amount","category"]]\
          .to_dict(orient="records")

    SYS=f"""You are a sharp, friendly personal finance advisor. The user has shared their real bank statement.

Period: {df['date'].min().strftime('%B %d')} – {df['date'].max().strftime('%B %d, %Y')}
Currency: {cur} | Spent: {sp2:,.2f} | Received: {rc2:,.2f} | Net: {nt2:+,.2f} | Transactions: {len(df)}

Spending by category: {json.dumps({k:round(v,2) for k,v in cb.items()})}
Top merchants: {json.dumps({k:round(v,2) for k,v in tm2.items()})}
Monthly budgets: {json.dumps(bgt)}
Recent 30 transactions: {json.dumps([{{**r,'date':str(r['date'])[:10]}} for r in rec])}

Be specific, concise, reference actual numbers. Use bullets. Flag budget overruns. Be actionable."""

    for msg in st.session_state.messages:
        cls="usr-b" if msg["role"]=="user" else "ai-b"
        icon="👤" if msg["role"]=="user" else "🤖"
        st.markdown(f'<div class="{cls}">{icon} {msg["content"]}</div>',unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        qs=["Where am I overspending?",f"How to save {cur} 500/month?",
            "Am I on budget?","Biggest expense categories?",
            "Analyze my food spending","Any subscriptions to cancel?",
            "Full financial summary","What should I cut first?"]
        cols=st.columns(4)
        for i,q in enumerate(qs):
            if cols[i%4].button(q,key=f"q{i}",use_container_width=True):
                st.session_state.messages.append({"role":"user","content":q})
                st.rerun()

    user_in=st.chat_input("Ask anything about your finances...")
    if user_in:
        st.session_state.messages.append({"role":"user","content":user_in})
        st.rerun()

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
        if st.button("🗑️ Clear chat"):
            st.session_state.messages=[]; st.rerun()
