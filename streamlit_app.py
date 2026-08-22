"""
Subba US Options Analyzer — Streamlit Cloud app.
Real-time MooMoo data via futu-api → FutuOpenD (exposed via ngrok TCP).

Setup:
  1. Run FutuOpenD on your Windows PC (already logged into MooMoo)
  2. Run: ngrok tcp 11111
  3. Copy ngrok host/port into this app's connection screen
     OR set in Streamlit secrets: FUTU_HOST / FUTU_PORT
"""
import os
import time
import logging
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

logging.basicConfig(level=logging.WARNING)

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


# ════════════════════════════════════════════════════════════════════════════
# CONNECTION SETUP
# ════════════════════════════════════════════════════════════════════════════

def _default_host():
    if hasattr(st, "secrets") and "FUTU_HOST" in st.secrets:
        return st.secrets["FUTU_HOST"]
    return os.environ.get("FUTU_HOST", "")


def _default_port():
    if hasattr(st, "secrets") and "FUTU_PORT" in st.secrets:
        return str(st.secrets["FUTU_PORT"])
    return os.environ.get("FUTU_PORT", "11111")


if "futu_host" not in st.session_state:
    st.session_state.futu_host = _default_host()
if "futu_port" not in st.session_state:
    st.session_state.futu_port = _default_port()
if "connected" not in st.session_state:
    st.session_state.connected = False


def try_connect(host: str, port: int) -> bool:
    try:
        import futu as ft
        ctx = ft.OpenQuoteContext(host=host, port=port)
        ret, data = ctx.get_global_state()
        ctx.close()
        return ret == ft.RET_OK
    except Exception:
        return False


# Show connection screen if not connected
if not st.session_state.connected:
    st.title("Connect to MooMoo")
    st.markdown("""
    This app connects to **MooMoo live data** via FutuOpenD running on your Windows PC.

    ### Steps to connect
    1. Open **FutuOpenD** on your Windows PC (log in with your MooMoo account)
    2. Install ngrok: [ngrok.com/download](https://ngrok.com/download)
    3. In a new terminal window, run:
       ```
       ngrok tcp 11111
       ```
    4. Copy the address shown — e.g. `0.tcp.ngrok.io:12345`
    5. Enter it below 👇
    """)

    col1, col2 = st.columns([3, 1])
    with col1:
        raw = st.text_input(
            "ngrok TCP address (host:port)",
            placeholder="0.tcp.ngrok.io:12345",
            value=f"{st.session_state.futu_host}:{st.session_state.futu_port}"
            if st.session_state.futu_host and st.session_state.futu_port
            else "",
        )
    with col2:
        st.write("")
        st.write("")
        connect_btn = st.button("Connect", type="primary")

    if connect_btn and raw.strip():
        parts = raw.strip().rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) == 2 else 11111
        with st.spinner(f"Connecting to {host}:{port}…"):
            ok = try_connect(host, port)
        if ok:
            st.session_state.futu_host = host
            st.session_state.futu_port = str(port)
            st.session_state.connected = True
            st.success("Connected! Loading app…")
            time.sleep(0.8)
            st.rerun()
        else:
            st.error(
                f"Cannot connect to FutuOpenD at {host}:{port}. "
                "Make sure FutuOpenD is running and ngrok TCP tunnel is active."
            )

    st.divider()
    st.caption("**No ngrok?** You can also run everything locally — FastAPI on localhost:8000 and the Next.js frontend on localhost:3000.")
    st.stop()


# ── Connected — import futu and set up helpers ───────────────────────────────
import futu as ft

FUTU_HOST = st.session_state.futu_host
FUTU_PORT = int(st.session_state.futu_port)
TRADE_ENV = ft.TrdEnv.PAPER if os.environ.get("TRADE_ENV", "PAPER") == "PAPER" else ft.TrdEnv.REAL


def get_quote_ctx():
    return ft.OpenQuoteContext(host=FUTU_HOST, port=FUTU_PORT)


def get_trade_ctx():
    return ft.OpenUSTradeContext(host=FUTU_HOST, port=FUTU_PORT)


def us(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if t.startswith("US.") else f"US.{t}"


# ════════════════════════════════════════════════════════════════════════════
# ANALYSIS HELPERS (ported from backend/routers/analysis.py)
# ════════════════════════════════════════════════════════════════════════════

def calc_pcr(chain_rows):
    ce = sum(r.get("open_interest", 0) for r in chain_rows if r.get("option_type") == "CALL")
    pe = sum(r.get("open_interest", 0) for r in chain_rows if r.get("option_type") == "PUT")
    return round(pe / ce, 4) if ce > 0 else 0.0


def calc_max_pain(chain_rows):
    strikes = sorted(set(r["strike"] for r in chain_rows))
    if not strikes:
        return 0.0
    by_strike = {}
    for r in chain_rows:
        s = r["strike"]
        if s not in by_strike:
            by_strike[s] = {"ce_oi": 0, "pe_oi": 0}
        if r.get("option_type") == "CALL":
            by_strike[s]["ce_oi"] += r.get("open_interest", 0)
        else:
            by_strike[s]["pe_oi"] += r.get("open_interest", 0)
    min_pain, mp_strike = float("inf"), strikes[0]
    for ts in strikes:
        pain = sum(
            v["ce_oi"] * (ts - s) if ts > s else v["pe_oi"] * (s - ts) if ts < s else 0
            for s, v in by_strike.items()
        )
        if pain < min_pain:
            min_pain, mp_strike = pain, ts
    return mp_strike


def score_signal(chain_rows, spot, pcr, max_pain):
    score = 0
    details = []

    # PCR
    if pcr >= 1.3:   score += 2; details.append(("PCR", f"{pcr:.2f}", "Bullish 🟢", "Heavy put writing = support floor"))
    elif pcr >= 1.0: score += 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bullish 🟡", "More puts = mild support"))
    elif pcr <= 0.7: score -= 2; details.append(("PCR", f"{pcr:.2f}", "Bearish 🔴", "Heavy call writing = resistance"))
    elif pcr < 1.0:  score -= 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bearish 🟡", "More calls = mild resistance"))
    else:            details.append(("PCR", f"{pcr:.2f}", "Neutral ⚪", "Balanced OI"))

    # Max Pain
    mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
    if mp_pct > 1.0:    score -= 2; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Bearish 🔴", "Spot well above MP — gravity pulls down"))
    elif mp_pct > 0.3:  score -= 1; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Mildly Bearish 🟡", "Spot slightly above MP"))
    elif mp_pct < -1.0: score += 2; details.append(("Max Pain", f"{mp_pct:.1f}%", "Bullish 🟢", "Spot well below MP — gravity pulls up"))
    elif mp_pct < -0.3: score += 1; details.append(("Max Pain", f"{mp_pct:.1f}%", "Mildly Bullish 🟡", "Spot slightly below MP"))
    else:               details.append(("Max Pain", f"{mp_pct:.1f}%", "Neutral ⚪", "Spot near Max Pain"))

    # OI Walls
    calls = sorted([r for r in chain_rows if r.get("option_type") == "CALL"], key=lambda x: x["strike"])
    puts  = sorted([r for r in chain_rows if r.get("option_type") == "PUT"],  key=lambda x: x["strike"])
    max_ce_oi = max((r.get("open_interest", 0) for r in calls), default=0)
    max_pe_oi = max((r.get("open_interest", 0) for r in puts),  default=0)
    max_ce_strike = next((r["strike"] for r in calls if r.get("open_interest", 0) == max_ce_oi), 0)
    max_pe_strike = next((r["strike"] for r in puts  if r.get("open_interest", 0) == max_pe_oi), 0)
    if spot > max_ce_strike and max_ce_strike:
        score += 1; details.append(("OI Walls", f"Spot {spot:.2f} > CE wall {max_ce_strike:.2f}", "Bullish 🟢", "Resistance cleared"))
    elif spot < max_pe_strike and max_pe_strike:
        score -= 1; details.append(("OI Walls", f"Spot {spot:.2f} < PE wall {max_pe_strike:.2f}", "Bearish 🔴", "Support broken"))
    else:
        details.append(("OI Walls", f"CE ${max_ce_strike:.2f} | PE ${max_pe_strike:.2f}", "Neutral ⚪", "Spot between walls"))

    if   score >=  4: signal = "STRONG BUY CALL 📈"
    elif score >=  2: signal = "BUY CALL 📈"
    elif score <= -4: signal = "STRONG BUY PUT 📉"
    elif score <= -2: signal = "BUY PUT 📉"
    else:             signal = "NEUTRAL — WAIT ⚖️"

    return signal, score, details, max_ce_strike, max_pe_strike


def signal_color(sig: str):
    s = sig.upper()
    if "STRONG BUY CALL" in s: return "#22c55e"
    if "BUY CALL" in s:        return "#86efac"
    if "STRONG BUY PUT" in s:  return "#ef4444"
    if "BUY PUT" in s:         return "#fca5a5"
    return "#94a3b8"


# ════════════════════════════════════════════════════════════════════════════
# DATA FETCH HELPERS (cached)
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spot(ticker: str) -> float:
    try:
        ctx = get_quote_ctx()
        ret, data = ctx.get_market_snapshot([us(ticker)])
        ctx.close()
        if ret == ft.RET_OK and len(data) > 0:
            return float(data.iloc[0].get("last_price", 0))
    except Exception:
        pass
    return 0.0


@st.cache_data(ttl=300, show_spinner=False)
def fetch_expirations(ticker: str):
    try:
        ctx = get_quote_ctx()
        ret, data = ctx.get_option_expiration_date(us(ticker))
        ctx.close()
        if ret == ft.RET_OK:
            return data["strike_time"].tolist()
    except Exception:
        pass
    return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_chain_rows(ticker: str, expiry: str):
    """Returns list of dicts with strike, option_type, OI, last, bid, ask, iv, delta."""
    try:
        ctx = get_quote_ctx()
        ret, chain_df = ctx.get_option_chain(
            code=us(ticker),
            index_option_type=ft.IndexOptionType.NORMAL,
            start=expiry, end=expiry,
        )
        if ret != ft.RET_OK:
            ctx.close()
            return []
        codes = chain_df["code"].tolist()
        rows = []
        for code in codes:
            meta = chain_df[chain_df["code"] == code].iloc[0]
            strike = float(meta.get("strike_price", 0))
            otype  = str(meta.get("option_type", "")).upper()
            sr, sd = ctx.get_market_snapshot([str(code)])
            if sr == ft.RET_OK and len(sd) > 0:
                s = sd.iloc[0]
                rows.append({
                    "code": str(code),
                    "strike": strike,
                    "option_type": "CALL" if "CALL" in otype else "PUT",
                    "last": float(s.get("last_price", 0)),
                    "bid":  float(s.get("bid_price",  0)),
                    "ask":  float(s.get("ask_price",  0)),
                    "mid":  round((float(s.get("bid_price", 0)) + float(s.get("ask_price", 0))) / 2, 2),
                    "open_interest": int(s.get("open_interest", 0)),
                    "volume": int(s.get("volume", 0)),
                    "iv":    float(s.get("implied_volatility", 0)),
                    "delta": float(s.get("delta", 0)),
                    "gamma": float(s.get("gamma", 0)),
                    "theta": float(s.get("theta", 0)),
                })
        ctx.close()
        return rows
    except Exception as e:
        st.error(f"Chain fetch error: {e}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshot(tickers_csv: str):
    try:
        syms = [us(t.strip()) for t in tickers_csv.split(",") if t.strip()]
        ctx = get_quote_ctx()
        ret, data = ctx.get_market_snapshot(syms)
        ctx.close()
        if ret == ft.RET_OK:
            return data
    except Exception:
        pass
    return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_funds():
    try:
        ctx = get_trade_ctx()
        ret, data = ctx.accinfo_query(trd_env=TRADE_ENV)
        ctx.close()
        if ret == ft.RET_OK:
            return data.iloc[0].to_dict()
    except Exception:
        pass
    return {}


@st.cache_data(ttl=120, show_spinner=False)
def fetch_positions():
    try:
        ctx = get_trade_ctx()
        ret, data = ctx.position_list_query(trd_env=TRADE_ENV)
        ctx.close()
        if ret == ft.RET_OK:
            return data
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📈 Subba US Options")
    st.markdown(f"<span style='color:#22c55e;font-size:0.8rem'>● Connected — {FUTU_HOST}:{FUTU_PORT}</span>", unsafe_allow_html=True)
    st.caption("MooMoo live data via FutuOpenD")

    page = st.radio(
        "Navigate",
        ["Dashboard", "Options Chain", "OI Signal", "Expiry Analyzer", "OI Scanner", "Smart Signal"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("Disconnect", key="disconnect"):
        st.session_state.connected = False
        st.session_state.futu_host = ""
        st.session_state.futu_port = "11111"
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("Dashboard")
    DEFAULT = "SPY,QQQ,IWM,AAPL,NVDA,TSLA,MSFT,AMZN"
    tickers_in = st.text_input("Tickers (comma-separated)", DEFAULT)

    col_r, _ = st.columns([1, 3])
    with col_r:
        refresh = st.button("Refresh Quotes")

    with st.spinner("Loading quotes…"):
        snap = fetch_snapshot(tickers_in)

    if snap is not None and len(snap) > 0:
        cols = st.columns(4)
        for i, (_, row) in enumerate(snap.iterrows()):
            code = str(row.get("code", "")).replace("US.", "")
            last = float(row.get("last_price", 0))
            chg  = float(row.get("change_rate", 0))
            cols[i % 4].metric(code, f"${last:.2f}", delta=f"{chg:+.2f}%", delta_color="normal")
    else:
        st.info("No quote data.")

    st.divider()
    st.subheader("Account")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Funds")
        funds = fetch_funds()
        if funds:
            st.metric("Cash",        f"${float(funds.get('cash', 0)):,.2f}")
            st.metric("Market Val",  f"${float(funds.get('market_val', 0)):,.2f}")
            st.metric("Total Assets",f"${float(funds.get('total_assets', 0)):,.2f}")
            st.metric("Unrealized P/L", f"${float(funds.get('unrealized_pl', 0)):+,.2f}")
        else:
            st.caption("Funds unavailable (PAPER env or trading context not accessible).")
    with c2:
        st.caption("Positions")
        pos = fetch_positions()
        if pos is not None and len(pos) > 0:
            show = [c for c in ["code","qty","cost_price","market_val","unrealized_pl"] if c in pos.columns]
            st.dataframe(pos[show].rename(columns={"code":"symbol","cost_price":"avg_cost"})
                         .style.format({"avg_cost":"${:.2f}","market_val":"${:.2f}","unrealized_pl":"${:.2f}"}),
                         use_container_width=True)
        else:
            st.caption("No open positions.")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OPTIONS CHAIN
# ════════════════════════════════════════════════════════════════════════════

elif page == "Options Chain":
    st.title("Options Chain")
    c1, c2 = st.columns([1, 2])
    with c1:
        ticker = st.text_input("Ticker", "AAPL").upper().strip()
    with st.spinner("Loading expirations…"):
        exps = fetch_expirations(ticker)
    if not exps:
        st.warning("No expirations. Check FutuOpenD connection.")
        st.stop()
    with c2:
        expiry = st.selectbox("Expiry", exps)

    with st.spinner(f"Loading {ticker} chain for {expiry}…"):
        rows = fetch_chain_rows(ticker, expiry)

    if not rows:
        st.info("No chain data returned.")
        st.stop()

    calls_df = pd.DataFrame([r for r in rows if r["option_type"] == "CALL"]).sort_values("strike")
    puts_df  = pd.DataFrame([r for r in rows if r["option_type"] == "PUT"]).sort_values("strike")

    if not calls_df.empty and not puts_df.empty:
        fig = go.Figure()
        fig.add_bar(x=calls_df["strike"], y=calls_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
        fig.add_bar(x=puts_df["strike"],  y=puts_df["open_interest"],  name="Puts OI",  marker_color="#ef4444")
        spot = fetch_spot(ticker)
        if spot:
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text=f"Spot {spot:.2f}")
        fig.update_layout(barmode="group", title="Open Interest by Strike",
                          paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                          font_color="#94a3b8", height=300)
        st.plotly_chart(fig, use_container_width=True)

    disp_cols = ["strike","last","bid","ask","volume","open_interest","iv","delta","gamma","theta"]
    tab_c, tab_p = st.tabs(["Calls", "Puts"])
    fmt = {"strike":"${:.2f}","last":"${:.2f}","bid":"${:.2f}","ask":"${:.2f}",
           "iv":"{:.1%}","delta":"{:.3f}","gamma":"{:.4f}","theta":"{:.4f}"}
    with tab_c:
        if not calls_df.empty:
            st.dataframe(calls_df[[c for c in disp_cols if c in calls_df.columns]]
                         .style.format({k:v for k,v in fmt.items() if k in calls_df.columns}),
                         use_container_width=True)
    with tab_p:
        if not puts_df.empty:
            st.dataframe(puts_df[[c for c in disp_cols if c in puts_df.columns]]
                         .style.format({k:v for k,v in fmt.items() if k in puts_df.columns}),
                         use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OI SIGNAL
# ════════════════════════════════════════════════════════════════════════════

elif page == "OI Signal":
    st.title("OI Signal")
    st.caption("PCR + Max Pain + OI Walls → directional bias for one expiry.")

    c1, c2 = st.columns([1, 2])
    with c1:
        ticker = st.text_input("Ticker", "AAPL").upper().strip()
    with st.spinner("Loading expirations…"):
        exps = fetch_expirations(ticker)
    if not exps:
        st.warning("No expirations.")
        st.stop()
    with c2:
        expiry = st.selectbox("Expiry", exps)

    if st.button("Analyze", type="primary"):
        with st.spinner(f"Fetching {ticker} chain for {expiry}… (may take 30–60s)"):
            rows = fetch_chain_rows(ticker, expiry)
            spot = fetch_spot(ticker)

        if not rows:
            st.warning("No chain data returned.")
            st.stop()

        pcr      = calc_pcr(rows)
        max_pain = calc_max_pain(rows)
        signal, score, details, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
        col = signal_color(signal)
        mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        # Banner
        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                            padding:16px 20px;margin-bottom:1rem">
              <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em">Signal</div>
              <div style="font-size:1.6rem;font-weight:700;color:{col}">{signal}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:6px">
                Score <b style="color:{col}">{score:+}</b> &nbsp;·&nbsp;
                PCR {pcr:.2f} &nbsp;·&nbsp;
                Max Pain ${max_pain:.2f} &nbsp;·&nbsp;
                Spot ${spot:.2f}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("PCR", f"{pcr:.2f}")
        m2.metric("Max Pain", f"${max_pain:.2f}")
        m3.metric("MP Dist%", f"{mp_pct:+.1f}%")
        m4.metric("CE Wall", f"${ce_wall:.0f}")
        m5.metric("PE Wall", f"${pe_wall:.0f}")

        # OI chart
        calls_r = [r for r in rows if r["option_type"] == "CALL"]
        puts_r  = [r for r in rows if r["option_type"] == "PUT"]
        # filter near ATM (±20 strikes)
        all_strikes = sorted(set(r["strike"] for r in rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        visible = set(all_strikes[max(0,atm_idx-20):atm_idx+21])
        calls_filt = [r for r in calls_r if r["strike"] in visible]
        puts_filt  = [r for r in puts_r  if r["strike"] in visible]

        if calls_filt or puts_filt:
            fig = go.Figure()
            if calls_filt:
                c_df = pd.DataFrame(calls_filt).sort_values("strike")
                fig.add_bar(x=c_df["strike"], y=c_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
            if puts_filt:
                p_df = pd.DataFrame(puts_filt).sort_values("strike")
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI", marker_color="#ef4444")
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot", line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike (ATM ±20)",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=340)
            st.plotly_chart(fig, use_container_width=True)

        # Signal factors table
        st.subheader("Signal Breakdown")
        st.dataframe(
            pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]),
            use_container_width=True,
        )

        # Trade recommendation
        all_strikes_near = sorted(all_strikes)
        gaps = [b - a for a, b in zip(all_strikes_near, all_strikes_near[1:])]
        gap = min(gaps) if gaps else 1.0
        is_call   = "CALL" in signal
        is_strong = "STRONG" in signal
        is_neutral = "NEUTRAL" in signal

        if not is_neutral:
            rec_strike = atm if is_strong else (atm + gap if is_call else atm - gap)
            otype = "CALL" if is_call else "PUT"
            cands = [r for r in rows if r["option_type"] == otype and abs(r["strike"] - rec_strike) < gap * 0.6]
            if not cands:
                cands = [r for r in rows if r["option_type"] == otype and abs(r["strike"] - atm) < gap * 0.6]
            ltp = cands[0]["last"] if cands else 0
            actual_strike = cands[0]["strike"] if cands else rec_strike
            sl     = round(ltp * 0.65, 2)
            target = round(ltp * 1.65, 2)
            rr     = round((target - ltp) / (ltp - sl), 1) if ltp > sl else 0

            st.subheader("Trade Recommendation")
            t1, t2, t3, t4, t5 = st.columns(5)
            t1.metric("Strike", f"${actual_strike:.0f}")
            t2.metric("LTP", f"${ltp:.2f}")
            t3.metric("Stop Loss", f"${sl:.2f}")
            t4.metric("Target", f"${target:.2f}")
            t5.metric("R:R", f"{rr:.1f}:1")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: EXPIRY ANALYZER
# ════════════════════════════════════════════════════════════════════════════

elif page == "Expiry Analyzer":
    st.title("Expiry Analyzer")
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.selectbox("Ticker", ["SPY","QQQ","IWM","AAPL","NVDA","TSLA","MSFT","AMZN","AMD","GOOGL"])
    with c2:
        offset = st.radio("Expiry", [0,1,2], format_func=lambda x:["Nearest","Next","Third"][x], horizontal=True)
    with c3:
        st.write("")
        go_btn = st.button("Analyze", type="primary")

    if go_btn:
        with st.spinner("Loading expirations…"):
            exps = fetch_expirations(ticker)
        if not exps or offset >= len(exps):
            st.warning("Not enough expirations available.")
            st.stop()
        expiry = exps[offset]
        st.caption(f"Analyzing expiry: **{expiry}**")

        with st.spinner(f"Fetching OI data for {ticker} {expiry}…"):
            rows = fetch_chain_rows(ticker, expiry)
            spot = fetch_spot(ticker)

        if not rows:
            st.warning("No data returned.")
            st.stop()

        pcr      = calc_pcr(rows)
        max_pain = calc_max_pain(rows)
        signal, score, details, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
        col = signal_color(signal)
        mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        # Rocket alert
        rocket_up   = mp_pct < -1.5 and pcr > 1.1
        rocket_down = mp_pct >  1.5 and pcr < 0.9
        if rocket_up:
            st.success("🚀 ROCKET UP — Spot well below Max Pain with bullish OI. Strong gravitational pull upward.")
        elif rocket_down:
            st.error("💣 ROCKET DOWN — Spot well above Max Pain with bearish OI. Strong gravitational pull downward.")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Spot", f"${spot:.2f}")
        m2.metric("Max Pain", f"${max_pain:.2f}")
        m3.metric("PCR", f"{pcr:.2f}")
        m4.metric("MP Dist%", f"{mp_pct:+.1f}%")
        m5.metric("CE Wall", f"${ce_wall:.0f}")
        m6.metric("PE Wall", f"${pe_wall:.0f}")

        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                            padding:12px 18px;margin:0.8rem 0">
              <span style="color:{col};font-size:1.3rem;font-weight:700">{signal}</span>
              &nbsp;&nbsp;<span style="color:#64748b">Score: <b style="color:{col}">{score:+}</b></span>
            </div>""",
            unsafe_allow_html=True,
        )

        # OI chart
        all_strikes = sorted(set(r["strike"] for r in rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        visible = set(all_strikes[max(0,atm_idx-20):atm_idx+21])
        c_df = pd.DataFrame([r for r in rows if r["option_type"]=="CALL" and r["strike"] in visible]).sort_values("strike")
        p_df = pd.DataFrame([r for r in rows if r["option_type"]=="PUT"  and r["strike"] in visible]).sort_values("strike")

        if not c_df.empty or not p_df.empty:
            fig = go.Figure()
            if not c_df.empty:
                fig.add_bar(x=c_df["strike"], y=c_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
            if not p_df.empty:
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI", marker_color="#ef4444")
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot", line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=320)
            st.plotly_chart(fig, use_container_width=True)

        # Key levels
        st.subheader("Key Levels")
        lvls = pd.DataFrame([
            ("Max Pain",            max_pain),
            ("CE Wall (Resistance)", ce_wall),
            ("PE Wall (Support)",    pe_wall),
            ("ATM Strike",          atm),
            ("Spot",                spot),
        ], columns=["Level","Price"])
        st.dataframe(lvls.style.format({"Price":"${:.2f}"}), use_container_width=True)

        st.subheader("Signal Factors")
        st.dataframe(pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]),
                     use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OI SCANNER
# ════════════════════════════════════════════════════════════════════════════

elif page == "OI Scanner":
    st.title("OI Scanner")
    st.caption("Scan multiple tickers — ranks by signal strength.")

    DEFAULT = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,SPY,QQQ"
    tickers_raw = st.text_area("Tickers (comma-separated)", DEFAULT, height=68)
    c1, c2 = st.columns([2, 1])
    with c1:
        offset = st.radio("Expiry", [0,1,2], format_func=lambda x:["Nearest","Next","Third"][x], horizontal=True)
    with c2:
        st.write("")
        scan_btn = st.button("Scan", type="primary")

    if scan_btn:
        tickers_list = [t.strip().upper() for t in tickers_raw.replace("\n","").split(",") if t.strip()]
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, tk in enumerate(tickers_list):
            status.caption(f"Scanning {tk}… ({i+1}/{len(tickers_list)})")
            try:
                exps = fetch_expirations(tk)
                if not exps or offset >= len(exps):
                    continue
                expiry = exps[offset]
                rows = fetch_chain_rows(tk, expiry)
                spot = fetch_spot(tk)
                if not rows or not spot:
                    continue
                pcr      = calc_pcr(rows)
                max_pain = calc_max_pain(rows)
                sig, score, _, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
                mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
                results.append({
                    "ticker": tk, "spot": spot, "expiry": expiry, "pcr": pcr,
                    "max_pain": max_pain, "mp_dist_pct": mp_pct,
                    "score": score, "signal": sig,
                    "ce_wall": ce_wall, "pe_wall": pe_wall,
                })
            except Exception:
                pass
            progress.progress((i + 1) / len(tickers_list))

        status.empty()
        progress.empty()

        if not results:
            st.warning("No results. Check FutuOpenD connection.")
        else:
            results.sort(key=lambda r: abs(r["score"]), reverse=True)
            st.success(f"Scanned {len(tickers_list)} tickers · {len(results)} results")
            df = pd.DataFrame(results)

            fig = px.bar(df, x="ticker", y="score", color="score",
                         color_continuous_scale=["#ef4444","#94a3b8","#22c55e"],
                         range_color=[-6,6], title="OI Score by Ticker")
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=260, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            display = df.copy()
            display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️", "", regex=True)
            st.dataframe(
                display.rename(columns={"ce_wall":"CE Wall","pe_wall":"PE Wall"})
                       .style.format({
                           "spot":"${:.2f}","pcr":"{:.2f}","max_pain":"${:.2f}",
                           "mp_dist_pct":"{:+.1f}%","CE Wall":"${:.0f}","PE Wall":"${:.0f}",
                       }),
                use_container_width=True,
            )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: SMART SIGNAL
# ════════════════════════════════════════════════════════════════════════════

elif page == "Smart Signal":
    st.title("Smart Signal")
    st.caption("Compares OI signals across all available expiries — finds the expiry with the strongest bias.")

    ticker = st.text_input("Ticker", "AAPL").upper().strip()

    if st.button("Analyze All Expiries", type="primary"):
        with st.spinner("Loading expirations…"):
            exps = fetch_expirations(ticker)
        if not exps:
            st.warning("No expirations found.")
            st.stop()

        scan_exps = exps[:6]
        spot = fetch_spot(ticker)
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, expiry in enumerate(scan_exps):
            status.caption(f"Scanning expiry {expiry}… ({i+1}/{len(scan_exps)})")
            rows = fetch_chain_rows(ticker, expiry)
            if rows and spot:
                pcr      = calc_pcr(rows)
                max_pain = calc_max_pain(rows)
                sig, score, _, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
                mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
                ce_oi = sum(r.get("open_interest",0) for r in rows if r["option_type"]=="CALL")
                pe_oi = sum(r.get("open_interest",0) for r in rows if r["option_type"]=="PUT")
                results.append({
                    "expiry": expiry, "pcr": pcr, "max_pain": max_pain, "signal": sig,
                    "score": score, "ce_wall": ce_wall, "pe_wall": pe_wall,
                    "mp_dist_pct": mp_pct, "ce_oi_k": ce_oi/1000, "pe_oi_k": pe_oi/1000,
                })
            progress.progress((i + 1) / len(scan_exps))

        status.empty()
        progress.empty()

        if not results:
            st.warning("No signal data returned.")
            st.stop()

        best = max(results, key=lambda r: abs(r["score"]))
        col = signal_color(best["signal"])
        st.markdown(
            f"""<div style="background:rgba(99,102,241,0.1);border:1px solid #6366f1;
                            border-radius:12px;padding:14px 20px;margin-bottom:1rem">
              <div style="font-size:0.7rem;color:#818cf8;text-transform:uppercase;letter-spacing:.1em">Strongest Signal</div>
              <div style="font-size:1.5rem;font-weight:700;color:{col}">{best['signal']}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">
                Expiry: <b style="color:#fff">{best['expiry']}</b> &nbsp;·&nbsp;
                Score: <b style="color:{col}">{best['score']:+}</b> &nbsp;·&nbsp;
                PCR: {best['pcr']:.2f} &nbsp;·&nbsp; Max Pain: ${best['max_pain']:.2f}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        df = pd.DataFrame(results)
        colors = [signal_color(r["signal"]) for r in results]
        fig = go.Figure(go.Bar(x=df["expiry"], y=df["score"], marker_color=colors))
        fig.update_layout(title="OI Score by Expiry", yaxis=dict(range=[-6,6]),
                          paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                          font_color="#94a3b8", height=260)
        st.plotly_chart(fig, use_container_width=True)

        display = df.copy()
        display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️","", regex=True)
        st.dataframe(
            display.rename(columns={"ce_wall":"CE Wall","pe_wall":"PE Wall",
                                    "ce_oi_k":"CE OI (K)","pe_oi_k":"PE OI (K)"})
                   .style.format({
                       "pcr":"{:.2f}","max_pain":"${:.2f}","mp_dist_pct":"{:+.1f}%",
                       "CE OI (K)":"{:.1f}K","PE OI (K)":"{:.1f}K",
                       "CE Wall":"${:.0f}","PE Wall":"${:.0f}",
                   }),
            use_container_width=True,
        )
