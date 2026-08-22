"""
Subba US Options Analyzer — Streamlit Cloud frontend.
All data from the FastAPI backend (futu-api / MooMoo live feed).

Configure BACKEND_URL in Streamlit secrets or environment:
  [secrets]
  BACKEND_URL = "https://your-fastapi-url"
"""
import os
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Subba US Options",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#0f172a; }
[data-testid="stSidebar"] { background:#1e293b; }
.block-container { padding-top:1.2rem; }
div[data-testid="metric-container"] {
  background:#1e293b; border:1px solid #334155;
  border-radius:12px; padding:12px 16px;
}
</style>
""", unsafe_allow_html=True)

# ── Backend URL ──────────────────────────────────────────────────────────────

BACKEND = (
    st.secrets.get("BACKEND_URL")
    if hasattr(st, "secrets") and "BACKEND_URL" in st.secrets
    else os.environ.get("BACKEND_URL", "http://localhost:8000")
).rstrip("/")


def _get(path: str, params: dict = None, timeout: int = 45):
    """Call FastAPI backend; return JSON or None on error."""
    try:
        r = requests.get(f"{BACKEND}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot reach backend at **{BACKEND}**. "
            "Start FastAPI + FutuOpenD locally and set BACKEND_URL in Streamlit secrets."
        )
        return None
    except Exception as exc:
        st.error(f"Backend error: {exc}")
        return None


# ── Cached data helpers ──────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def api_expirations(ticker: str):
    data = _get(f"/api/options/{ticker}/expirations")
    return data["expirations"] if data else []


@st.cache_data(ttl=60, show_spinner=False)
def api_chain(ticker: str, expiry: str):
    return _get(f"/api/options/{ticker}/chain", {"expiry": expiry})


@st.cache_data(ttl=60, show_spinner=False)
def api_oi_signal(ticker: str, expiry: str, strikes_atm: int = 20):
    return _get(
        f"/api/options/{ticker}/oi-signal",
        {"expiry": expiry, "strikes_atm": strikes_atm},
    )


@st.cache_data(ttl=60, show_spinner=False)
def api_expiry_analyze(ticker: str, expiry_offset: int = 0):
    return _get("/api/expiry/analyze", {"ticker": ticker, "expiry_offset": expiry_offset})


@st.cache_data(ttl=60, show_spinner=False)
def api_scanner(tickers: str, expiry_offset: int = 0):
    return _get(
        "/api/scanner/scan",
        {"tickers": tickers, "expiry_offset": expiry_offset},
        timeout=120,
    )


@st.cache_data(ttl=60, show_spinner=False)
def api_quotes(tickers: str):
    return _get("/api/quotes/snapshot", {"tickers": tickers})


@st.cache_data(ttl=300, show_spinner=False)
def api_positions():
    return _get("/api/account/positions")


@st.cache_data(ttl=300, show_spinner=False)
def api_account_funds():
    return _get("/api/account/funds")


# ── Signal helpers ────────────────────────────────────────────────────────────

def signal_color(signal: str) -> str:
    s = signal.upper()
    if "STRONG BUY CALL" in s:
        return "🟢"
    if "BUY CALL" in s:
        return "🟩"
    if "STRONG BUY PUT" in s:
        return "🔴"
    if "BUY PUT" in s:
        return "🟥"
    return "⚪"


def score_color_hex(score: float) -> str:
    if score >= 4:
        return "#22c55e"
    if score >= 2:
        return "#86efac"
    if score <= -4:
        return "#ef4444"
    if score <= -2:
        return "#fca5a5"
    return "#94a3b8"


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — PAGE PICKER
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📈 Subba US Options")
    st.caption("Real-time via MooMoo / FutuOpenD")
    page = st.radio(
        "Navigate",
        [
            "Dashboard",
            "Options Chain",
            "OI Signal",
            "Expiry Analyzer",
            "OI Scanner",
            "Smart Signal",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"Backend: `{BACKEND}`")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("Dashboard")
    st.caption("Live MooMoo snapshot for key US instruments.")

    DEFAULT_TICKERS = "SPY,QQQ,IWM,AAPL,NVDA,TSLA,MSFT,AMZN"
    tickers_input = st.text_input("Tickers (comma-separated)", DEFAULT_TICKERS, key="dash_tickers")

    if st.button("Refresh", key="dash_refresh") or True:
        with st.spinner("Fetching quotes…"):
            data = api_quotes(tickers_input)

        if data and "quotes" in data:
            quotes = data["quotes"]
            cols = st.columns(min(len(quotes), 4))
            for i, q in enumerate(quotes):
                col = cols[i % 4]
                chg = q.get("change_pct", 0)
                col.metric(
                    q.get("symbol", "—"),
                    f"${q.get('last', 0):.2f}",
                    delta=f"{chg:+.2f}%" if chg else None,
                    delta_color="normal",
                )
        else:
            st.info("No quote data returned — check backend connection.")

    st.divider()
    st.subheader("Account Summary")
    col1, col2 = st.columns(2)

    with col1:
        with st.spinner("Loading funds…"):
            funds = api_account_funds()
        if funds:
            st.metric("Cash", f"${funds.get('cash', 0):,.2f}")
            st.metric("Market Value", f"${funds.get('market_val', 0):,.2f}")
            st.metric("Total Assets", f"${funds.get('total_assets', 0):,.2f}")
        else:
            st.caption("Funds unavailable (backend/FutuOpenD not reachable).")

    with col2:
        with st.spinner("Loading positions…"):
            pos = api_positions()
        if pos and pos.get("positions"):
            df = pd.DataFrame(pos["positions"])
            df = df.rename(columns={"code": "symbol", "cost_price": "avg_cost"})
            show_cols = [c for c in ["symbol","qty","avg_cost","market_val","unrealized_pl"] if c in df.columns]
            st.dataframe(df[show_cols].style.format({
                "avg_cost": "${:.2f}", "market_val": "${:.2f}", "unrealized_pl": "${:.2f}"
            }), use_container_width=True)
        else:
            st.caption("No open positions or backend unavailable.")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OPTIONS CHAIN
# ════════════════════════════════════════════════════════════════════════════

elif page == "Options Chain":
    st.title("Options Chain")

    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input("Ticker", "AAPL", key="chain_ticker").upper().strip()

    with st.spinner("Loading expirations…"):
        exps = api_expirations(ticker)

    if not exps:
        st.warning("No expirations returned. Backend or FutuOpenD may be offline.")
        st.stop()

    with col2:
        expiry = st.selectbox("Expiry", exps, key="chain_expiry")

    with st.spinner(f"Loading {ticker} chain for {expiry}…"):
        chain = api_chain(ticker, expiry)

    if not chain:
        st.stop()

    calls = pd.DataFrame(chain.get("calls", []))
    puts  = pd.DataFrame(chain.get("puts",  []))

    if calls.empty and puts.empty:
        st.info("No chain data returned.")
        st.stop()

    # ── OI chart ──
    if not calls.empty and not puts.empty:
        fig = go.Figure()
        fig.add_bar(x=calls["strike"], y=calls["open_interest"], name="Calls OI",
                    marker_color="#3b82f6")
        fig.add_bar(x=puts["strike"],  y=puts["open_interest"],  name="Puts OI",
                    marker_color="#ef4444")
        fig.update_layout(
            title="Open Interest by Strike",
            barmode="group",
            paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
            font_color="#94a3b8", height=320,
        )
        st.plotly_chart(fig, use_container_width=True)

    tab_calls, tab_puts = st.tabs(["Calls", "Puts"])

    display_cols = ["strike", "last", "bid", "ask", "volume", "open_interest",
                    "iv", "delta", "gamma", "theta"]

    with tab_calls:
        if not calls.empty:
            show = [c for c in display_cols if c in calls.columns]
            st.dataframe(calls[show].style.format({
                "strike": "${:.2f}", "last": "${:.2f}", "bid": "${:.2f}",
                "ask": "${:.2f}", "iv": "{:.1%}", "delta": "{:.3f}",
                "gamma": "{:.4f}", "theta": "{:.4f}",
            }), use_container_width=True)

    with tab_puts:
        if not puts.empty:
            show = [c for c in display_cols if c in puts.columns]
            st.dataframe(puts[show].style.format({
                "strike": "${:.2f}", "last": "${:.2f}", "bid": "${:.2f}",
                "ask": "${:.2f}", "iv": "{:.1%}", "delta": "{:.3f}",
                "gamma": "{:.4f}", "theta": "{:.4f}",
            }), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OI SIGNAL
# ════════════════════════════════════════════════════════════════════════════

elif page == "OI Signal":
    st.title("OI Signal")
    st.caption("PCR + Max Pain + OI Walls → directional bias for one expiry.")

    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input("Ticker", "AAPL", key="sig_ticker").upper().strip()

    with st.spinner("Loading expirations…"):
        exps = api_expirations(ticker)
    if not exps:
        st.warning("No expirations returned.")
        st.stop()

    with col2:
        expiry = st.selectbox("Expiry", exps, key="sig_expiry")

    if st.button("Analyze", key="sig_go"):
        with st.spinner(f"Analyzing {ticker} {expiry}…"):
            sig = api_oi_signal(ticker, expiry)

        if not sig:
            st.stop()

        # ── Summary banner ──
        icon = signal_color(sig.get("signal", ""))
        score = sig.get("score", 0)
        color = "#22c55e" if score > 0 else "#ef4444" if score < 0 else "#94a3b8"
        st.markdown(
            f"""
            <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                        padding:16px 20px;margin-bottom:1rem;">
              <div style="font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.08em">Signal</div>
              <div style="font-size:1.6rem;font-weight:700;color:{color}">{icon} {sig.get('signal','—')}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">
                Score: <b style="color:{color}">{score:+}</b> &nbsp;·&nbsp;
                PCR: {sig.get('pcr',0):.2f} &nbsp;·&nbsp;
                Max Pain: ${sig.get('max_pain',0):.2f} &nbsp;·&nbsp;
                Spot: ${sig.get('spot',0):.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Metrics row ──
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("PCR", f"{sig.get('pcr',0):.2f}")
        c2.metric("Max Pain", f"${sig.get('max_pain',0):.2f}")
        mp_dist = ((sig.get("spot",0) - sig.get("max_pain",0)) / sig.get("max_pain",1)) * 100
        c3.metric("MP Dist%", f"{mp_dist:+.1f}%")
        c4.metric("CE Wall", f"${sig.get('max_call_wall',0):.0f}")
        c5.metric("PE Wall", f"${sig.get('max_put_wall',0):.0f}")

        # ── Trade recommendation ──
        rec = sig.get("recommendation")
        if rec:
            st.subheader("Trade Recommendation")
            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("Strike", f"${rec.get('strike',0):.0f}")
            r2.metric("Entry (LTP)", f"${rec.get('entry_ltp',0):.2f}")
            r3.metric("Stop Loss", f"${rec.get('stop_loss',0):.2f}")
            r4.metric("Target", f"${rec.get('target',0):.2f}")
            r5.metric("R:R", rec.get("risk_reward", "—"))

        # ── OI breakdown chart ──
        breakdown = sig.get("oi_breakdown", [])
        if breakdown:
            df_bd = pd.DataFrame(breakdown)
            fig = go.Figure()
            fig.add_bar(x=df_bd["strike"], y=df_bd["ce_oi"], name="Calls OI",
                        marker_color="#3b82f6")
            fig.add_bar(x=df_bd["strike"], y=df_bd["pe_oi"], name="Puts OI",
                        marker_color="#ef4444")
            if sig.get("spot"):
                fig.add_vline(x=sig["spot"], line_dash="dash", line_color="#f59e0b",
                              annotation_text=f"Spot {sig['spot']:.2f}")
            if sig.get("max_pain"):
                fig.add_vline(x=sig["max_pain"], line_dash="dot", line_color="#a855f7",
                              annotation_text=f"MaxPain {sig['max_pain']:.2f}")
            fig.update_layout(
                barmode="group", title="OI by Strike (ATM ±20)",
                paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                font_color="#94a3b8", height=340,
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Signal breakdown table ──
        factors = sig.get("factors", [])
        if factors:
            st.subheader("Signal Factors")
            st.dataframe(pd.DataFrame(factors), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: EXPIRY ANALYZER
# ════════════════════════════════════════════════════════════════════════════

elif page == "Expiry Analyzer":
    st.title("Expiry Analyzer")
    st.caption("Deep-dive into the nearest expiry for any ticker.")

    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.selectbox("Ticker", ["SPY","QQQ","IWM","AAPL","NVDA","TSLA","MSFT","AMZN","AMD","GOOGL"])
    with col2:
        expiry_offset = st.radio("Expiry", [0, 1, 2], format_func=lambda x: ["Nearest","Next","Third"][x], horizontal=True)
    with col3:
        st.write("")
        analyze = st.button("Analyze", key="exp_go")

    if analyze:
        with st.spinner(f"Analyzing {ticker} expiry #{expiry_offset}…"):
            data = api_expiry_analyze(ticker, expiry_offset)

        if not data:
            st.stop()

        # ── Rocket banner ──
        if data.get("rocket_up"):
            st.success("🚀 ROCKET UP — Spot is below Max Pain with bullish OI structure. Strong pull upward expected.")
        elif data.get("rocket_down"):
            st.error("💣 ROCKET DOWN — Spot is above Max Pain with bearish OI structure. Strong pull downward expected.")

        # ── Key metrics ──
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Spot", f"${data.get('spot',0):.2f}")
        m2.metric("Max Pain", f"${data.get('max_pain',0):.2f}")
        m3.metric("PCR", f"{data.get('pcr',0):.2f}")
        mp_dist = ((data.get("spot",0) - data.get("max_pain",0)) / max(data.get("max_pain",1),1)) * 100
        m4.metric("MP Dist%", f"{mp_dist:+.1f}%")
        m5.metric("CE Wall", f"${data.get('max_call_wall',0):.0f}")
        m6.metric("PE Wall", f"${data.get('max_put_wall',0):.0f}")

        score = data.get("score", 0)
        signal = data.get("signal", "—")
        icon = signal_color(signal)
        color = "#22c55e" if score > 0 else "#ef4444" if score < 0 else "#94a3b8"
        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                            padding:12px 18px;margin:0.5rem 0">
              <span style="color:{color};font-size:1.3rem;font-weight:700">{icon} {signal}</span>
              &nbsp;&nbsp;<span style="color:#64748b">Score: <b style="color:{color}">{score:+}</b></span>
              &emsp;<span style="color:#94a3b8;font-size:0.85rem">Expiry: {data.get('expiry','—')}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── OI chart ──
        breakdown = data.get("oi_breakdown", [])
        if breakdown:
            df_bd = pd.DataFrame(breakdown)
            fig = go.Figure()
            fig.add_bar(x=df_bd["strike"], y=df_bd["ce_oi"], name="Calls OI", marker_color="#3b82f6")
            fig.add_bar(x=df_bd["strike"], y=df_bd["pe_oi"], name="Puts OI", marker_color="#ef4444")
            if data.get("spot"):
                fig.add_vline(x=data["spot"], line_dash="dash", line_color="#f59e0b",
                              annotation_text="Spot")
            if data.get("max_pain"):
                fig.add_vline(x=data["max_pain"], line_dash="dot", line_color="#a855f7",
                              annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=340)
            st.plotly_chart(fig, use_container_width=True)

        # ── Key levels table ──
        levels = data.get("key_levels")
        if levels:
            st.subheader("Key Levels")
            lvl_df = pd.DataFrame([
                {"Level": "Support 1", "Price": levels.get("support1", 0)},
                {"Level": "Support 2", "Price": levels.get("support2", 0)},
                {"Level": "Resistance 1", "Price": levels.get("resistance1", 0)},
                {"Level": "Resistance 2", "Price": levels.get("resistance2", 0)},
                {"Level": "Max Pain", "Price": data.get("max_pain", 0)},
                {"Level": "CE Wall (Resistance)", "Price": data.get("max_call_wall", 0)},
                {"Level": "PE Wall (Support)", "Price": data.get("max_put_wall", 0)},
            ])
            st.dataframe(lvl_df.style.format({"Price": "${:.2f}"}), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OI SCANNER
# ════════════════════════════════════════════════════════════════════════════

elif page == "OI Scanner":
    st.title("OI Scanner")
    st.caption("Scan multiple tickers for OI signals, ranked by strength.")

    DEFAULT_TICKERS = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,SPY,QQQ,IWM,JPM,NFLX,AVGO,CRM"
    tickers = st.text_area("Tickers (comma-separated)", DEFAULT_TICKERS, height=68)
    col1, col2 = st.columns([2, 1])
    with col1:
        expiry_offset = st.radio("Expiry", [0, 1, 2],
                                  format_func=lambda x: ["Nearest","Next Week","Third"][x],
                                  horizontal=True)
    with col2:
        scan_btn = st.button("Scan", key="scan_go", type="primary")

    if scan_btn:
        n = len([t.strip() for t in tickers.split(",") if t.strip()])
        with st.spinner(f"Scanning {n} tickers… this may take 30–60 seconds."):
            result = api_scanner(tickers.replace("\n", "").replace(" ", ""), expiry_offset)

        if not result:
            st.stop()

        rows = result.get("results", [])
        if not rows:
            st.info("No results returned. Check FutuOpenD connection.")
        else:
            st.success(f"Scanned {result.get('scanned',0)} tickers · {result.get('returned',0)} results")
            df = pd.DataFrame(rows)

            # Score bar chart
            fig = px.bar(
                df, x="ticker", y="score",
                color="score",
                color_continuous_scale=["#ef4444","#94a3b8","#22c55e"],
                range_color=[-6, 6],
                title="OI Score by Ticker",
            )
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=280, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # Table
            display = df[["ticker","spot","expiry","pcr","max_pain","mp_dist_pct",
                           "score","signal","max_call_wall","max_put_wall"]].copy()
            display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️", "", regex=True)

            def color_score(val):
                if val >= 4: return "color:#22c55e;font-weight:bold"
                if val >= 2: return "color:#86efac"
                if val <= -4: return "color:#ef4444;font-weight:bold"
                if val <= -2: return "color:#fca5a5"
                return "color:#94a3b8"

            st.dataframe(
                display.style
                    .format({
                        "spot": "${:.2f}", "pcr": "{:.2f}", "max_pain": "${:.2f}",
                        "mp_dist_pct": "{:+.1f}%", "max_call_wall": "${:.0f}",
                        "max_put_wall": "${:.0f}",
                    })
                    .applymap(color_score, subset=["score"]),
                use_container_width=True,
            )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: SMART SIGNAL
# ════════════════════════════════════════════════════════════════════════════

elif page == "Smart Signal":
    st.title("Smart Signal")
    st.caption("Compares OI signals across all available expiries — finds the expiry with the strongest directional bias.")

    ticker = st.text_input("Ticker", "AAPL", key="ss_ticker").upper().strip()

    if st.button("Analyze All Expiries", key="ss_go", type="primary"):
        with st.spinner("Loading expirations…"):
            exps = api_expirations(ticker)

        if not exps:
            st.warning("No expirations found.")
            st.stop()

        scan_exps = exps[:6]
        st.info(f"Scanning {len(scan_exps)} expiries for {ticker}…")

        results = []
        progress = st.progress(0)
        for i, expiry in enumerate(scan_exps):
            sig = api_oi_signal(ticker, expiry)
            if sig:
                spot = sig.get("spot", 0)
                mp = sig.get("max_pain", 0)
                results.append({
                    "expiry": sig.get("expiry", expiry),
                    "pcr": sig.get("pcr", 0),
                    "max_pain": mp,
                    "signal": sig.get("signal", "—"),
                    "score": sig.get("score", 0),
                    "max_call_wall": sig.get("max_call_wall", 0),
                    "max_put_wall": sig.get("max_put_wall", 0),
                    "mp_dist_pct": ((spot - mp) / mp * 100) if mp else 0,
                    "total_ce_oi": sig.get("total_ce_oi", 0),
                    "total_pe_oi": sig.get("total_pe_oi", 0),
                })
            progress.progress((i + 1) / len(scan_exps))

        if not results:
            st.warning("No signal data returned.")
            st.stop()

        df = pd.DataFrame(results)

        # Best signal
        best = max(results, key=lambda r: abs(r["score"]))
        icon = signal_color(best["signal"])
        score = best["score"]
        color = "#22c55e" if score > 0 else "#ef4444" if score < 0 else "#94a3b8"
        st.markdown(
            f"""<div style="background:rgba(99,102,241,0.1);border:1px solid #6366f1;
                            border-radius:12px;padding:14px 20px;margin-bottom:1rem">
              <div style="font-size:0.7rem;color:#818cf8;text-transform:uppercase;letter-spacing:.1em">Strongest Signal</div>
              <div style="font-size:1.5rem;font-weight:700;color:{color}">{icon} {best['signal']}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">
                Expiry: <b style="color:#fff">{best['expiry']}</b> &nbsp;·&nbsp;
                Score: <b style="color:{color}">{score:+}</b> &nbsp;·&nbsp;
                PCR: {best['pcr']:.2f} &nbsp;·&nbsp; Max Pain: ${best['max_pain']:.2f}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # Score bar chart
        colors = [score_color_hex(r["score"]) for r in results]
        fig = go.Figure(go.Bar(
            x=df["expiry"], y=df["score"],
            marker_color=colors,
        ))
        fig.update_layout(
            title="OI Score by Expiry", yaxis=dict(range=[-6, 6]),
            paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
            font_color="#94a3b8", height=280,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        display = df.copy()
        display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️", "", regex=True)
        display["ce_oi_k"] = (display["total_ce_oi"] / 1000).round(1)
        display["pe_oi_k"] = (display["total_pe_oi"] / 1000).round(1)

        st.dataframe(
            display[["expiry","score","signal","pcr","max_pain","mp_dist_pct",
                      "ce_oi_k","pe_oi_k","max_call_wall","max_put_wall"]]
            .rename(columns={"ce_oi_k":"CE OI (K)","pe_oi_k":"PE OI (K)",
                              "max_call_wall":"CE Wall","max_put_wall":"PE Wall"})
            .style.format({
                "pcr": "{:.2f}", "max_pain": "${:.2f}", "mp_dist_pct": "{:+.1f}%",
                "CE OI (K)": "{:.1f}K", "PE OI (K)": "{:.1f}K",
                "CE Wall": "${:.0f}", "PE Wall": "${:.0f}",
            }),
            use_container_width=True,
        )
