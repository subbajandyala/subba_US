"""
Subba US Options Analyzer — Streamlit Cloud app.
Real-time MooMoo data via gateway-free REST API (webapi.moomoo.com).
AppKey Ed25519 signature authentication — no FutuOpenD, no OAuth login.

Streamlit secrets required:
  MOOMOO_APP_KEY_ID = "2262a22a2faaf381a2e740db195e4864"
  MOOMOO_PRIVATE_KEY = \"\"\"-----BEGIN PRIVATE KEY-----
  ...your Ed25519 private key...
  -----END PRIVATE KEY-----\"\"\"
"""
import os, time, base64, secrets as _sec, urllib.parse
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

MOOMOO_API = "https://webapi.moomoo.com/api/v1.0"

# ── Secrets ───────────────────────────────────────────────────────────────────

def _secret(key: str, default: str = "") -> str:
    if hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets[key])
    return os.environ.get(key, default)

APP_KEY_ID      = _secret("MOOMOO_APP_KEY_ID")
PRIVATE_KEY_PEM = _secret("MOOMOO_PRIVATE_KEY")

if not APP_KEY_ID or not PRIVATE_KEY_PEM:
    st.title("Subba US Options — Setup")
    st.error("Add **MOOMOO_APP_KEY_ID** and **MOOMOO_PRIVATE_KEY** to Streamlit secrets.")
    st.markdown("""
    In Streamlit Cloud → App **⋮ Menu → Settings → Secrets**, add:
    ```toml
    MOOMOO_APP_KEY_ID = "2262a22a2faaf381a2e740db195e4864"
    MOOMOO_PRIVATE_KEY = \"\"\"-----BEGIN PRIVATE KEY-----
    paste_your_private_key_here
    -----END PRIVATE KEY-----\"\"\"
    ```
    Get both from **open.moomoo.com → AppKey Management**.
    """)
    st.stop()


# ── Ed25519 signing ───────────────────────────────────────────────────────────

@st.cache_resource
def _load_pk():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    pem = PRIVATE_KEY_PEM.strip()
    if pem.startswith("-----"):
        return load_pem_private_key(pem.encode(), password=None)
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(pem))


_srv_time_offset_ms: int = 0   # adjusted once on first successful call

def _synced_ts_ms() -> str:
    """Return current millisecond timestamp, adjusted for server-time offset."""
    return str(int(time.time() * 1000) + _srv_time_offset_ms)


def _build_qs(params: dict) -> str:
    if not params:
        return ""
    return "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(params.items())
    )


def _sign_request(method: str, canonical_path: str, qs: str) -> tuple[str, str, str, str]:
    """Returns (ts_ms, nonce, sig_b64, canonical) for a request."""
    ts_ms = _synced_ts_ms()
    nonce = _sec.token_hex(16)
    canonical = f"{ts_ms}\n{method}\n{canonical_path}\n{qs}\n"
    sig_b64 = base64.b64encode(_load_pk().sign(canonical.encode())).decode()
    return ts_ms, nonce, sig_b64, canonical


def _make_headers(ts_ms: str, nonce: str, sig_b64: str) -> dict:
    return {
        "X-Api-Key":     APP_KEY_ID,
        "X-Timestamp":   ts_ms,
        "X-Nonce":       nonce,
        "Authorization": sig_b64,
        "Content-Type":  "application/json",
    }


# ── REST helpers ──────────────────────────────────────────────────────────────

def _try_sync_server_time():
    """One-shot attempt to sync local clock to MooMoo server time (no auth needed)."""
    global _srv_time_offset_ms
    try:
        r = requests.get(f"{MOOMOO_API}/server-time", timeout=5)
        if r.ok:
            d = r.json()
            srv = d.get("data") or d
            # field may be "server_time", "timestamp", "time", or "serverTime"
            for key in ("server_time", "serverTime", "timestamp", "time"):
                if key in srv:
                    _srv_time_offset_ms = int(srv[key]) - int(time.time() * 1000)
                    break
    except Exception:
        pass


_try_sync_server_time()   # run once at module load


def _get(path: str, params: dict = None, timeout: int = 30):
    """GET request to MooMoo REST API with AppKey Ed25519 auth.

    Tries two canonical-path variants:
      1. Full URL path:  /api/v1.0{path}
      2. Endpoint only:  {path}   (e.g. /quote/option-expiration-date)
    """
    qs      = _build_qs(params)
    url     = f"{MOOMOO_API}{path}" + (f"?{qs}" if qs else "")

    for canonical_path in (f"/api/v1.0{path}", path):
        ts_ms, nonce, sig_b64, canonical = _sign_request("GET", canonical_path, qs)
        try:
            r = requests.get(url, headers=_make_headers(ts_ms, nonce, sig_b64),
                             timeout=timeout)
            if r.ok:
                return r.json()
            body = r.text
            # -12006 = invalid signature — try other path variant before giving up
            try:
                code = r.json().get("code", 0)
            except Exception:
                code = 0
            if code == -12006 and canonical_path == f"/api/v1.0{path}":
                continue   # retry with shorter path
            # permanent failure — surface it
            st.error(f"API {path} → {r.status_code}")
            with st.expander("Error detail"):
                st.code(body)
                st.caption(f"Canonical path tried: `{canonical_path}`")
                st.caption(f"Canonical string:\n```\n{canonical}```")
                st.caption(f"Server-time offset: {_srv_time_offset_ms} ms")
            return None
        except requests.RequestException as e:
            st.error(f"Network error {path}: {e}")
            return None

    # both variants failed
    st.error(f"API {path} → auth failed (both path variants tried)")
    return None


def us(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if t.startswith("US.") else f"US.{t}"


# ── Cached data ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshot(tickers_csv: str):
    code_list = ",".join(us(t.strip()) for t in tickers_csv.split(",") if t.strip())
    return _get("/quote/market-snapshot", {"code_list": code_list})


@st.cache_data(ttl=300, show_spinner=False)
def fetch_expirations(ticker: str):
    data = _get("/quote/option-expiration-date", {"code": us(ticker)})
    if data and "data" in data:
        return data["data"].get("option_expiration_date_list", [])
    return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_option_chain(ticker: str, expiry: str):
    return _get("/quote/option-chain", {
        "code": us(ticker),
        "start_strike_time": expiry,
        "end_strike_time":   expiry,
    }, timeout=60)


def _parse_chain_rows(chain_data, expiry: str):
    if not chain_data or "data" not in chain_data:
        return []
    rows = []
    for item in chain_data["data"].get("option_chain", []):
        for opt_type in ["call", "put"]:
            opts = item.get(opt_type, [])
            if not isinstance(opts, list):
                opts = [opts] if opts else []
            for opt in opts:
                if not opt:
                    continue
                rows.append({
                    "code":          opt.get("code", ""),
                    "strike":        float(opt.get("strike_price", 0)),
                    "option_type":   "CALL" if opt_type == "call" else "PUT",
                    "last":          float(opt.get("last_price",        0)),
                    "bid":           float(opt.get("bid_price",         0)),
                    "ask":           float(opt.get("ask_price",         0)),
                    "open_interest": int(opt.get("open_interest",       0)),
                    "volume":        int(opt.get("volume",              0)),
                    "iv":            float(opt.get("implied_volatility", 0)),
                    "delta":         float(opt.get("delta",             0)),
                    "gamma":         float(opt.get("gamma",             0)),
                    "theta":         float(opt.get("theta",             0)),
                })
    return rows


def _spot_from_snapshot(snap_data, ticker: str) -> float:
    if not snap_data or "data" not in snap_data:
        return 0.0
    for item in snap_data.get("data", {}).get("snapshot_list", []):
        if us(ticker) in item.get("code", ""):
            return float(item.get("last_price", 0))
    return 0.0


# ── Analysis helpers ──────────────────────────────────────────────────────────

def calc_pcr(rows):
    ce = sum(r["open_interest"] for r in rows if r["option_type"] == "CALL")
    pe = sum(r["open_interest"] for r in rows if r["option_type"] == "PUT")
    return round(pe / ce, 4) if ce > 0 else 0.0


def calc_max_pain(rows):
    strikes = sorted(set(r["strike"] for r in rows))
    if not strikes:
        return 0.0
    by_s = {}
    for r in rows:
        s = r["strike"]
        if s not in by_s:
            by_s[s] = {"ce": 0, "pe": 0}
        by_s[s]["ce" if r["option_type"] == "CALL" else "pe"] += r["open_interest"]
    best, best_s = float("inf"), strikes[0]
    for ts in strikes:
        pain = sum(
            v["ce"] * (ts - s) if ts > s else v["pe"] * (s - ts) if ts < s else 0
            for s, v in by_s.items()
        )
        if pain < best:
            best, best_s = pain, ts
    return best_s


def score_signal(rows, spot, pcr, max_pain):
    score, details = 0, []
    if   pcr >= 1.3: score += 2; details.append(("PCR", f"{pcr:.2f}", "Bullish 🟢",       "Heavy put writing"))
    elif pcr >= 1.0: score += 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bullish 🟡", "More puts"))
    elif pcr <= 0.7: score -= 2; details.append(("PCR", f"{pcr:.2f}", "Bearish 🔴",        "Heavy call writing"))
    elif pcr <  1.0: score -= 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bearish 🟡", "More calls"))
    else:                         details.append(("PCR", f"{pcr:.2f}", "Neutral ⚪",         "Balanced OI"))

    mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
    if   mp_pct >  1.0: score -= 2; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Bearish 🔴",       "Spot above MP"))
    elif mp_pct >  0.3: score -= 1; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Mildly Bearish 🟡",""))
    elif mp_pct < -1.0: score += 2; details.append(("Max Pain", f"{mp_pct:.1f}%",  "Bullish 🟢",       "Spot below MP"))
    elif mp_pct < -0.3: score += 1; details.append(("Max Pain", f"{mp_pct:.1f}%",  "Mildly Bullish 🟡",""))
    else:                            details.append(("Max Pain", f"{mp_pct:.1f}%",  "Neutral ⚪",        "Spot near MP"))

    calls = sorted([r for r in rows if r["option_type"] == "CALL"], key=lambda x: x["strike"])
    puts  = sorted([r for r in rows if r["option_type"] == "PUT"],  key=lambda x: x["strike"])
    max_ce_oi = max((r["open_interest"] for r in calls), default=0)
    max_pe_oi = max((r["open_interest"] for r in puts),  default=0)
    ce_wall = next((r["strike"] for r in calls if r["open_interest"] == max_ce_oi), 0)
    pe_wall = next((r["strike"] for r in puts  if r["open_interest"] == max_pe_oi), 0)
    if   spot > ce_wall > 0:  score += 1; details.append(("OI Walls", f"Spot > CE ${ce_wall:.0f}", "Bullish 🟢",  "Resistance cleared"))
    elif 0 < spot < pe_wall:  score -= 1; details.append(("OI Walls", f"Spot < PE ${pe_wall:.0f}", "Bearish 🔴",  "Support broken"))
    else:                                  details.append(("OI Walls", f"CE ${ce_wall:.0f} | PE ${pe_wall:.0f}", "Neutral ⚪", "Spot between walls"))

    if   score >=  4: sig = "STRONG BUY CALL 📈"
    elif score >=  2: sig = "BUY CALL 📈"
    elif score <= -4: sig = "STRONG BUY PUT 📉"
    elif score <= -2: sig = "BUY PUT 📉"
    else:             sig = "NEUTRAL — WAIT ⚖️"
    return sig, score, details, ce_wall, pe_wall


def sig_color(sig: str) -> str:
    s = sig.upper()
    if "STRONG BUY CALL" in s: return "#22c55e"
    if "BUY CALL"        in s: return "#86efac"
    if "STRONG BUY PUT"  in s: return "#ef4444"
    if "BUY PUT"         in s: return "#fca5a5"
    return "#94a3b8"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📈 Subba US Options")
    st.markdown("<span style='color:#22c55e;font-size:0.8rem'>● Connected — MooMoo REST API</span>",
                unsafe_allow_html=True)
    st.caption(f"AppKey: …{APP_KEY_ID[-8:]}")
    page = st.radio(
        "Navigate",
        ["Dashboard", "Options Chain", "OI Signal", "Expiry Analyzer", "OI Scanner", "Smart Signal"],
        label_visibility="collapsed",
    )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════

if page == "Dashboard":
    st.title("Dashboard")
    DEFAULT = "SPY,QQQ,IWM,AAPL,NVDA,TSLA,MSFT,AMZN"
    tickers_in = st.text_input("Tickers (comma-separated)", DEFAULT)
    st.button("Refresh", key="dash_refresh")

    with st.spinner("Loading quotes…"):
        snap = fetch_snapshot(tickers_in)

    if snap and "data" in snap:
        snap_list = snap["data"].get("snapshot_list", [])
        if snap_list:
            cols = st.columns(4)
            for i, item in enumerate(snap_list):
                code = str(item.get("code", "")).replace("US.", "")
                last = float(item.get("last_price", 0))
                chg  = float(item.get("change_rate", 0))
                cols[i % 4].metric(code, f"${last:.2f}", delta=f"{chg:+.2f}%", delta_color="normal")
        else:
            st.info("No snapshot data returned.")
            with st.expander("Raw API response"):
                st.json(snap)
    else:
        st.info("No data — check API connection or secret values.")
        if snap:
            with st.expander("Raw API response"):
                st.json(snap)


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
        st.warning("No expirations returned.")
        st.stop()
    with c2:
        expiry = st.selectbox("Expiry", exps)

    with st.spinner(f"Loading {ticker} chain for {expiry}…"):
        chain_raw = fetch_option_chain(ticker, expiry)
        snap_raw  = fetch_snapshot(ticker)

    rows = _parse_chain_rows(chain_raw, expiry)
    spot = _spot_from_snapshot(snap_raw, ticker)

    if not rows:
        st.info("No chain data returned.")
        if chain_raw:
            with st.expander("Raw API response"):
                st.json(chain_raw)
        st.stop()

    calls_df = pd.DataFrame([r for r in rows if r["option_type"] == "CALL"]).sort_values("strike")
    puts_df  = pd.DataFrame([r for r in rows if r["option_type"] == "PUT"]).sort_values("strike")

    if not calls_df.empty and not puts_df.empty:
        fig = go.Figure()
        fig.add_bar(x=calls_df["strike"], y=calls_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
        fig.add_bar(x=puts_df["strike"],  y=puts_df["open_interest"],  name="Puts OI",  marker_color="#ef4444")
        if spot:
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text=f"Spot {spot:.2f}")
        fig.update_layout(barmode="group", title="Open Interest by Strike",
                          paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                          font_color="#94a3b8", height=300)
        st.plotly_chart(fig, use_container_width=True)

    disp = ["strike","last","bid","ask","volume","open_interest","iv","delta","gamma","theta"]
    fmt  = {"strike":"${:.2f}","last":"${:.2f}","bid":"${:.2f}","ask":"${:.2f}",
            "iv":"{:.1%}","delta":"{:.3f}","gamma":"{:.4f}","theta":"{:.4f}"}
    tab_c, tab_p = st.tabs(["Calls", "Puts"])
    with tab_c:
        if not calls_df.empty:
            cols = [c for c in disp if c in calls_df.columns]
            st.dataframe(calls_df[cols].style.format({k: v for k, v in fmt.items() if k in cols}),
                         use_container_width=True)
    with tab_p:
        if not puts_df.empty:
            cols = [c for c in disp if c in puts_df.columns]
            st.dataframe(puts_df[cols].style.format({k: v for k, v in fmt.items() if k in cols}),
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
        st.warning("No expirations returned.")
        st.stop()
    with c2:
        expiry = st.selectbox("Expiry", exps)

    if st.button("Analyze", type="primary"):
        with st.spinner(f"Fetching OI data for {ticker} {expiry}…"):
            chain_raw = fetch_option_chain(ticker, expiry)
            snap_raw  = fetch_snapshot(ticker)

        rows = _parse_chain_rows(chain_raw, expiry)
        spot = _spot_from_snapshot(snap_raw, ticker)

        if not rows:
            st.warning("No chain data returned.")
            if chain_raw:
                with st.expander("Raw API response"):
                    st.json(chain_raw)
            st.stop()

        pcr      = calc_pcr(rows)
        max_pain = calc_max_pain(rows)
        signal, score, details, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
        col  = sig_color(signal)
        mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                            padding:16px 20px;margin-bottom:1rem">
              <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em">Signal</div>
              <div style="font-size:1.6rem;font-weight:700;color:{col}">{signal}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:6px">
                Score <b style="color:{col}">{score:+}</b> &nbsp;·&nbsp;
                PCR {pcr:.2f} &nbsp;·&nbsp; Max Pain ${max_pain:.2f} &nbsp;·&nbsp; Spot ${spot:.2f}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("PCR",      f"{pcr:.2f}")
        m2.metric("Max Pain", f"${max_pain:.2f}")
        m3.metric("MP Dist%", f"{mp_pct:+.1f}%")
        m4.metric("CE Wall",  f"${ce_wall:.0f}")
        m5.metric("PE Wall",  f"${pe_wall:.0f}")

        all_strikes = sorted(set(r["strike"] for r in rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        visible = set(all_strikes[max(0, atm_idx-20):atm_idx+21])
        c_df = pd.DataFrame([r for r in rows if r["option_type"]=="CALL" and r["strike"] in visible]).sort_values("strike")
        p_df = pd.DataFrame([r for r in rows if r["option_type"]=="PUT"  and r["strike"] in visible]).sort_values("strike")

        if not c_df.empty or not p_df.empty:
            fig = go.Figure()
            if not c_df.empty:
                fig.add_bar(x=c_df["strike"], y=c_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
            if not p_df.empty:
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI",  marker_color="#ef4444")
            fig.add_vline(x=spot,     line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot",  line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike (ATM ±20)",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=320)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Signal Breakdown")
        st.dataframe(pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]),
                     use_container_width=True)

        is_call    = "CALL"    in signal
        is_strong  = "STRONG"  in signal
        is_neutral = "NEUTRAL" in signal
        if not is_neutral:
            gaps = [b - a for a, b in zip(all_strikes, all_strikes[1:])]
            gap  = min(gaps) if gaps else 1.0
            rec_strike = atm if is_strong else (atm + gap if is_call else atm - gap)
            otype  = "CALL" if is_call else "PUT"
            cands  = [r for r in rows if r["option_type"] == otype and abs(r["strike"] - rec_strike) < gap * 0.6]
            ltp    = cands[0]["last"]   if cands else 0
            actual = cands[0]["strike"] if cands else rec_strike
            sl     = round(ltp * 0.65, 2)
            target = round(ltp * 1.65, 2)
            rr     = round((target - ltp) / (ltp - sl), 1) if ltp > sl else 0
            st.subheader("Trade Recommendation")
            t1, t2, t3, t4, t5 = st.columns(5)
            t1.metric("Strike",    f"${actual:.0f}")
            t2.metric("LTP",       f"${ltp:.2f}")
            t3.metric("Stop Loss", f"${sl:.2f}")
            t4.metric("Target",    f"${target:.2f}")
            t5.metric("R:R",       f"{rr:.1f}:1")


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
            st.warning("Not enough expirations.")
            st.stop()
        expiry = exps[offset]
        st.caption(f"Expiry: **{expiry}**")

        with st.spinner(f"Fetching {ticker} OI data…"):
            chain_raw = fetch_option_chain(ticker, expiry)
            snap_raw  = fetch_snapshot(ticker)

        rows = _parse_chain_rows(chain_raw, expiry)
        spot = _spot_from_snapshot(snap_raw, ticker)

        if not rows:
            st.warning("No data returned.")
            if chain_raw:
                with st.expander("Raw API response"):
                    st.json(chain_raw)
            st.stop()

        pcr      = calc_pcr(rows)
        max_pain = calc_max_pain(rows)
        signal, score, details, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
        col    = sig_color(signal)
        mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        if mp_pct < -1.5 and pcr > 1.1:
            st.success("🚀 ROCKET UP — Spot well below Max Pain with bullish OI.")
        elif mp_pct > 1.5 and pcr < 0.9:
            st.error("💣 ROCKET DOWN — Spot well above Max Pain with bearish OI.")

        m1,m2,m3,m4,m5,m6 = st.columns(6)
        m1.metric("Spot",      f"${spot:.2f}")
        m2.metric("Max Pain",  f"${max_pain:.2f}")
        m3.metric("PCR",       f"{pcr:.2f}")
        m4.metric("MP Dist%",  f"{mp_pct:+.1f}%")
        m5.metric("CE Wall",   f"${ce_wall:.0f}")
        m6.metric("PE Wall",   f"${pe_wall:.0f}")

        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                            padding:12px 18px;margin:.6rem 0">
              <span style="color:{col};font-size:1.3rem;font-weight:700">{signal}</span>
              &nbsp;&nbsp;<span style="color:#64748b">Score: <b style="color:{col}">{score:+}</b></span>
            </div>""",
            unsafe_allow_html=True,
        )

        all_strikes = sorted(set(r["strike"] for r in rows))
        atm = min(all_strikes, key=lambda x: abs(x - spot)) if all_strikes else spot
        atm_idx = all_strikes.index(atm) if atm in all_strikes else 0
        visible = set(all_strikes[max(0, atm_idx-20):atm_idx+21])
        c_df = pd.DataFrame([r for r in rows if r["option_type"]=="CALL" and r["strike"] in visible]).sort_values("strike")
        p_df = pd.DataFrame([r for r in rows if r["option_type"]=="PUT"  and r["strike"] in visible]).sort_values("strike")

        if not c_df.empty or not p_df.empty:
            fig = go.Figure()
            if not c_df.empty:
                fig.add_bar(x=c_df["strike"], y=c_df["open_interest"], name="Calls OI", marker_color="#3b82f6")
            if not p_df.empty:
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI",  marker_color="#ef4444")
            fig.add_vline(x=spot,     line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot",  line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=300)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Signal Factors")
        st.dataframe(pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]),
                     use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OI SCANNER
# ════════════════════════════════════════════════════════════════════════════

elif page == "OI Scanner":
    st.title("OI Scanner")
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
        results  = []
        progress = st.progress(0)
        status   = st.empty()

        for i, tk in enumerate(tickers_list):
            status.caption(f"Scanning {tk}… ({i+1}/{len(tickers_list)})")
            exps = fetch_expirations(tk)
            if not exps or offset >= len(exps):
                progress.progress((i+1)/len(tickers_list))
                continue
            expiry    = exps[offset]
            chain_raw = fetch_option_chain(tk, expiry)
            snap_raw  = fetch_snapshot(tk)
            rows = _parse_chain_rows(chain_raw, expiry)
            spot = _spot_from_snapshot(snap_raw, tk)
            if rows and spot:
                pcr      = calc_pcr(rows)
                max_pain = calc_max_pain(rows)
                sig, score, _, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
                mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
                results.append({"ticker":tk,"spot":spot,"expiry":expiry,"pcr":pcr,
                                 "max_pain":max_pain,"mp_dist_pct":mp_pct,
                                 "score":score,"signal":sig,"ce_wall":ce_wall,"pe_wall":pe_wall})
            progress.progress((i+1)/len(tickers_list))

        status.empty(); progress.empty()

        if not results:
            st.warning("No results.")
        else:
            results.sort(key=lambda r: abs(r["score"]), reverse=True)
            st.success(f"Scanned {len(tickers_list)} tickers · {len(results)} results")
            df  = pd.DataFrame(results)
            fig = px.bar(df, x="ticker", y="score", color="score",
                         color_continuous_scale=["#ef4444","#94a3b8","#22c55e"],
                         range_color=[-6,6], title="OI Score by Ticker")
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=240, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            display = df.copy()
            display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️","", regex=True)
            st.dataframe(
                display.rename(columns={"ce_wall":"CE Wall","pe_wall":"PE Wall"})
                       .style.format({"spot":"${:.2f}","pcr":"{:.2f}","max_pain":"${:.2f}",
                                      "mp_dist_pct":"{:+.1f}%","CE Wall":"${:.0f}","PE Wall":"${:.0f}"}),
                use_container_width=True,
            )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: SMART SIGNAL
# ════════════════════════════════════════════════════════════════════════════

elif page == "Smart Signal":
    st.title("Smart Signal")
    st.caption("Compares OI signals across all available expiries.")
    ticker = st.text_input("Ticker", "AAPL").upper().strip()

    if st.button("Analyze All Expiries", type="primary"):
        with st.spinner("Loading expirations…"):
            exps = fetch_expirations(ticker)
        if not exps:
            st.warning("No expirations found.")
            st.stop()

        scan_exps = exps[:6]
        snap_raw  = fetch_snapshot(ticker)
        spot      = _spot_from_snapshot(snap_raw, ticker)
        results   = []
        progress  = st.progress(0)
        status    = st.empty()

        for i, expiry in enumerate(scan_exps):
            status.caption(f"Scanning {expiry}… ({i+1}/{len(scan_exps)})")
            chain_raw = fetch_option_chain(ticker, expiry)
            rows = _parse_chain_rows(chain_raw, expiry)
            if rows and spot:
                pcr      = calc_pcr(rows)
                max_pain = calc_max_pain(rows)
                sig, score, _, ce_wall, pe_wall = score_signal(rows, spot, pcr, max_pain)
                mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
                ce_oi  = sum(r["open_interest"] for r in rows if r["option_type"]=="CALL")
                pe_oi  = sum(r["open_interest"] for r in rows if r["option_type"]=="PUT")
                results.append({"expiry":expiry,"pcr":pcr,"max_pain":max_pain,"signal":sig,
                                 "score":score,"ce_wall":ce_wall,"pe_wall":pe_wall,
                                 "mp_dist_pct":mp_pct,"ce_oi_k":ce_oi/1000,"pe_oi_k":pe_oi/1000})
            progress.progress((i+1)/len(scan_exps))

        status.empty(); progress.empty()

        if not results:
            st.warning("No data returned.")
            st.stop()

        best = max(results, key=lambda r: abs(r["score"]))
        col  = sig_color(best["signal"])
        st.markdown(
            f"""<div style="background:rgba(99,102,241,0.1);border:1px solid #6366f1;
                            border-radius:12px;padding:14px 20px;margin-bottom:1rem">
              <div style="font-size:0.7rem;color:#818cf8;text-transform:uppercase;letter-spacing:.1em">Strongest Signal</div>
              <div style="font-size:1.5rem;font-weight:700;color:{col}">{best['signal']}</div>
              <div style="font-size:0.85rem;color:#94a3b8;margin-top:4px">
                Expiry <b style="color:#fff">{best['expiry']}</b> &nbsp;·&nbsp;
                Score <b style="color:{col}">{best['score']:+}</b> &nbsp;·&nbsp;
                PCR {best['pcr']:.2f} &nbsp;·&nbsp; Max Pain ${best['max_pain']:.2f}
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

        df = pd.DataFrame(results)
        colors = [sig_color(r["signal"]) for r in results]
        fig = go.Figure(go.Bar(x=df["expiry"], y=df["score"], marker_color=colors))
        fig.update_layout(title="OI Score by Expiry", yaxis=dict(range=[-6,6]),
                          paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                          font_color="#94a3b8", height=240)
        st.plotly_chart(fig, use_container_width=True)

        display = df.copy()
        display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️","", regex=True)
        st.dataframe(
            display.rename(columns={"ce_wall":"CE Wall","pe_wall":"PE Wall",
                                    "ce_oi_k":"CE OI (K)","pe_oi_k":"PE OI (K)"})
                   .style.format({"pcr":"{:.2f}","max_pain":"${:.2f}","mp_dist_pct":"{:+.1f}%",
                                  "CE OI (K)":"{:.1f}K","PE OI (K)":"{:.1f}K",
                                  "CE Wall":"${:.0f}","PE Wall":"${:.0f}"}),
            use_container_width=True,
        )
