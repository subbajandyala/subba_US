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
import os, time, json, base64, hashlib, secrets as _sec, urllib.parse
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
    try:
        return str(st.secrets[key])
    except Exception:
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


def _signed_headers(method, path, qs, body_bytes):
    """AppKey signature per open.moomoo.com Getting Started:
    signing string = timestamp_ms \\n METHOD \\n /api/v1.0/path \\n raw_query \\n sha256_hex(body) (empty if no body)."""
    ts_ms = str(int(time.time() * 1000))
    body_hash = hashlib.sha256(body_bytes).hexdigest() if body_bytes else ""
    canonical = "{}\n{}\n/api/v1.0{}\n{}\n{}".format(ts_ms, method, path, qs, body_hash)
    sig = base64.b64encode(_load_pk().sign(canonical.encode())).decode()
    return {
        "X-Api-Key":     APP_KEY_ID,
        "X-Timestamp":   ts_ms,
        "X-Nonce":       _sec.token_hex(16),
        "Authorization": sig,
        "Content-Type":  "application/json",
    }, canonical


# ── REST helpers ──────────────────────────────────────────────────────────────

def _request(method, path, params=None, body=None, timeout=30, quiet=False):
    qs = ""
    if params:
        qs = "&".join(
            "{}={}".format(k, urllib.parse.quote(str(v), safe=""))
            for k, v in sorted(params.items())
        )
    body_bytes = json.dumps(body, separators=(",", ":")).encode() if body is not None else b""
    headers, canonical = _signed_headers(method, path, qs, body_bytes)
    url = "{}{}".format(MOOMOO_API, path) + ("?{}".format(qs) if qs else "")
    try:
        r = requests.request(method, url, headers=headers, data=body_bytes or None, timeout=timeout)
    except requests.RequestException as exc:
        if not quiet:
            st.error("Network error {}: {}".format(path, exc))
        return None
    if quiet and not r.ok:
        return None

    if r.ok:
        j = r.json()
        rc = j.get("ret_code", 0) if isinstance(j, dict) else 0
        if rc != 0:
            if not quiet:
                st.error("API {} {} → ret_code {} — {}".format(method, path, rc, j.get("ret_msg", "")))
                with st.expander("Error detail"):
                    st.json(j)
            return None
        return j

    st.error("API {} {} → {}".format(method, path, r.status_code))
    with st.expander("Error detail"):
        st.code(r.text)
        st.caption("Signing string:\n```\n{}\n```".format(canonical))
    return None


def _get(path, params=None, timeout=30):
    return _request("GET", path, params=params, timeout=timeout)


def _post(path, body, timeout=60, quiet=False):
    return _request("POST", path, body=body, timeout=timeout, quiet=quiet)


def us(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if t.startswith("US.") else f"US.{t}"


# ── Cached data ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def fetch_snapshot(tickers_csv):
    code_list = [us(t.strip()) for t in tickers_csv.split(",") if t.strip()]
    return _post("/quote/stock-quote", {"code_list": code_list})


@st.cache_data(ttl=60, show_spinner=False)
def fetch_market_snapshots(codes):
    """Bid/ask, OI, volume, IV and Greeks for any codes (POST /quote/snapshot, 400 per call)."""
    out = []
    codes = list(codes)
    for i in range(0, len(codes), 400):
        payload = _post("/quote/snapshot", {"code_list": codes[i:i + 400]})
        if payload and "data" in payload:
            out.extend(payload["data"].get("snapshot_list") or [])
    return out


def _to_ymd(date_str):
    """Normalise any date/datetime/timestamp string to YYYY-MM-DD."""
    s = str(date_str).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    return s


@st.cache_data(ttl=300, show_spinner=False)
def fetch_expirations(ticker):
    data = _get("/quote/{}/option-expiration".format(us(ticker)))
    if not data or "data" not in data:
        return []
    d = data["data"]
    lst = d.get("expiration_list") or d.get("option_expiration_date_list") or []
    dates = []
    for item in lst:
        if isinstance(item, dict):
            raw = item.get("strike_time") or item.get("date") or ""
        elif isinstance(item, str):
            raw = item
        else:
            raw = ""
        if raw:
            dates.append(_to_ymd(raw))
    return [x for x in dates if x]


@st.cache_data(ttl=60, show_spinner=False)
def fetch_option_chain(ticker, expiry):
    """Contracts for one expiry, enriched with live quotes.
    GET /quote/{symbol}/option-chain only returns codes and strikes, so prices,
    OI and Greeks come from /quote/snapshot and are merged into each contract."""
    chain = _get("/quote/{}/option-chain".format(us(ticker)), {"start": expiry, "end": expiry}, timeout=60)
    if not chain or "data" not in chain:
        return chain
    contracts = chain["data"].get("option_chain") or []
    snaps = {s.get("code"): s for s in fetch_market_snapshots(tuple(c["code"] for c in contracts))}
    for c in contracts:
        c.update({k: v for k, v in snaps.get(c["code"], {}).items() if k not in ("option_type", "name")})
    return chain


def _contract_row(opt, option_type_str):
    try:
        return {
            "code":          opt.get("code", ""),
            "strike":        float(opt.get("strike_price", 0) or 0),
            "option_type":   option_type_str,
            "last":          float(opt.get("last_price",        0) or 0),
            "bid":           float(opt.get("bid_price",         0) or 0),
            "ask":           float(opt.get("ask_price",         0) or 0),
            "open_interest": int(opt.get("option_open_interest") or opt.get("open_interest") or 0),
            "volume":        int(opt.get("volume",              0) or 0),
            "iv":            float(opt.get("option_implied_volatility") or opt.get("implied_volatility") or 0) / 100,
            "delta":         float(opt.get("delta",             0) or 0),
            "gamma":         float(opt.get("gamma",             0) or 0),
            "theta":         float(opt.get("theta",             0) or 0),
        }
    except (TypeError, ValueError):
        return None


def _parse_chain_rows(chain_data, expiry: str):
    if not chain_data or "data" not in chain_data:
        return []
    rows = []
    items = chain_data["data"].get("option_chain", [])
    for item in items:
        if not isinstance(item, dict):
            continue
        # Flat structure: each item is one CALL or PUT contract
        if "option_type" in item or "type" in item:
            raw_type = item.get("option_type") or item.get("type", 0)
            # 1=CALL, 2=PUT; or string "CALL"/"PUT"/"call"/"put"
            if str(raw_type) in ("1", "CALL", "call"):
                otype = "CALL"
            elif str(raw_type) in ("2", "PUT", "put"):
                otype = "PUT"
            else:
                continue
            row = _contract_row(item, otype)
            if row:
                rows.append(row)
        else:
            # Nested structure: item has "call" and/or "put" sub-lists
            for key, label in [("call", "CALL"), ("put", "PUT")]:
                opts = item.get(key, [])
                if not isinstance(opts, list):
                    opts = [opts] if opts else []
                for opt in opts:
                    if opt:
                        row = _contract_row(opt, label)
                        if row:
                            rows.append(row)
    return rows


def _spot_from_snapshot(snap_data, ticker: str) -> float:
    if not snap_data or "data" not in snap_data:
        return 0.0
    d = snap_data["data"]
    items = d.get("quote_list") or d.get("snapshot_list") or []
    for item in items:
        if us(ticker) in item.get("code", ""):
            return float(item.get("last_price", 0) or item.get("cur_price", 0))
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
        ["Dashboard", "Options Chain", "OI Signal", "Expiry Analyzer", "OI Scanner", "Smart Signal",
         "Options Radar", "Radar Results"],
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
        d = snap["data"]
        snap_list = d.get("quote_list") or d.get("snapshot_list") or []
        if snap_list:
            cols = st.columns(4)
            for i, item in enumerate(snap_list):
                code = str(item.get("code", "")).replace("US.", "")
                last = float(item.get("last_price", 0) or item.get("cur_price", 0))
                prev = float(item.get("prev_close_price", 0) or 0)
                chg  = float(item.get("change_rate", 0) or 0) or ((last - prev) / prev * 100 if prev else 0.0)
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


# ════════════════════════════════════════════════════════════════════════════
# OPTIONS RADAR — data helpers
# ════════════════════════════════════════════════════════════════════════════

import glob as _glob
import radar_engine as radar

RADAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "radar")


def _rows(payload, *keys):
    if not payload or "data" not in payload:
        return []
    d = payload["data"]
    for k in keys:
        if d.get(k):
            return d[k]
    return []


def fetch_option_snapshots(codes):
    """Greeks, bid/ask, OI and volume for option codes."""
    return fetch_market_snapshots(tuple(codes))


def fetch_underlyings(tickers):
    out = []
    for i in range(0, len(tickers), 150):
        out.extend(_rows(fetch_snapshot(",".join(tickers[i:i + 150])), "quote_list", "snapshot_list"))
    return out


def fetch_most_active(limit, min_volume, max_dte):
    """MooMoo option screener sorted by volume — the only source of the daily OI change."""
    strategy = {
        "market_category_list": [0],
        "filter_group_list": [
            {"option_list": [{"indicator_type": 2011, "indicator_value": {"value_interval": {"min_value": min_volume}}}]},
            {"option_list": [{"indicator_type": 1002, "indicator_value": {"value_interval": {"min_value": 0, "max_value": max_dte}}}]},
        ],
    }
    body = {"strategy": strategy, "limit": limit,
            "field_filter": {"option_name": "x", "volume": 1, "open_interest": 1, "oi_day_chg": 1, "left_day": 1}}
    return _rows(_post("/quote/option-screen", body), "option_list")


def fetch_universe_codes(tickers, n_expiries, strikes_each_side):
    """Fallback when the screener is unavailable: near-ATM contracts of the next expiries per ticker."""
    codes = []
    spots = {q.get("code"): float(q.get("last_price", 0) or 0) for q in fetch_underlyings(tickers)}
    for tk in tickers:
        spot = spots.get(us(tk), 0)
        for exp in fetch_expirations(tk)[:n_expiries]:
            chain = _rows(fetch_option_chain(tk, exp), "option_chain")
            strikes = sorted({float(c.get("strike_price", 0)) for c in chain})
            if not strikes or not spot:
                continue
            atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
            keep = set(strikes[max(0, atm_i - strikes_each_side): atm_i + strikes_each_side + 1])
            codes += [c["code"] for c in chain if float(c.get("strike_price", 0)) in keep]
    return codes


def _previous_oi():
    """OI per code from the latest saved scan, used for OI change in fallback mode."""
    files = sorted(_glob.glob(os.path.join(RADAR_DIR, "*_contracts.csv")))
    if not files:
        return {}
    prev = pd.read_csv(files[-1], usecols=["code", "oi"])
    return dict(zip(prev["code"], prev["oi"]))


def _save_scan(tag, contracts, bias, picks):
    os.makedirs(RADAR_DIR, exist_ok=True)
    stamp = pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d_%H%M")
    base = os.path.join(RADAR_DIR, "{}_{}".format(stamp, tag))
    contracts.to_csv(base + "_contracts.csv", index=False)
    bias.to_csv(base + "_bias.csv", index=False)
    picks.to_csv(base + "_picks.csv", index=False)
    return base


def _color_signal(styler):
    fn = getattr(styler, "map", None) or styler.applymap   # Styler.applymap was renamed to map
    return fn(_signal_style, subset=["signal"])


def _signal_style(v):
    s = str(v)
    if "STRONG BUY CALL" in s: return "color:#22c55e;font-weight:700"
    if "BUY CALL" in s:        return "color:#86efac"
    if "STRONG BUY PUT" in s:  return "color:#ef4444;font-weight:700"
    if "BUY PUT" in s:         return "color:#fca5a5"
    return "color:#94a3b8"


RADAR_HELP = """
**How to read it**

| OI | Option price (after removing what delta + theta explain) | Reading | For the stock |
|---|---|---|---|
| ↑ | ↑ | Long buildup (buyers) | Call → bullish · Put → bearish |
| ↑ | ↓ | Short buildup (writers) | Call → resistance · Put → support |
| ↓ | ↑ | Short covering | Call → bullish · Put → bearish |
| ↓ | ↓ | Long unwinding | no read |

- **Fresh** = volume > open interest (new positions today). **Stealth** = big volume, small price move.
- Options with 0–1 days left are shown but **not** used for direction (decay swamps the signal).
- A ticker needs ≥3 active contracts with both calls and puts, otherwise **LOW DATA**.
- **Buyer quality (0–100)** penalises delta outside 0.30–0.65, wide bid/ask, fast theta decay, 0 DTE, >21 DTE, OI < 1,000.

Research tool — one day of signals proves nothing. Track results in **Radar Results** for weeks before trusting a reading.
"""


# ════════════════════════════════════════════════════════════════════════════
# PAGE: OPTIONS RADAR
# ════════════════════════════════════════════════════════════════════════════

if page == "Options Radar":
    st.title("Options Radar")
    st.caption("Most active US options · where open interest was added · Greeks-based contract pick")
    with st.expander("How it works"):
        st.markdown(RADAR_HELP)

    mode = st.radio("Universe", ["Most active (MooMoo screener)", "My tickers"], horizontal=True)
    c1, c2, c3 = st.columns(3)
    if mode.startswith("Most"):
        limit = c1.slider("Contracts", 50, 400, 300, 50)
        min_vol = c2.number_input("Min volume", 100, 100000, 2000, 500)
        max_dte = c3.slider("Max days to expiry", 1, 90, 45)
    else:
        tickers_in = st.text_input("Tickers", "SPY,QQQ,IWM,NVDA,TSLA,AAPL,AMZN,META,MSFT,AMD")
        n_exp = c1.slider("Expiries per ticker", 1, 4, 2)
        width = c2.slider("Strikes each side of ATM", 2, 15, 6)

    if st.button("Run scan", type="primary"):
        with st.spinner("Fetching option data from MooMoo…"):
            screen = []
            if mode.startswith("Most"):
                screen = fetch_most_active(int(limit), int(min_vol), int(max_dte))
                codes = [r["code"] for r in screen]
                if not codes:
                    st.warning("Screener endpoint returned nothing — switch to **My tickers** mode.")
                    st.stop()
            else:
                tickers = [t.strip().upper() for t in tickers_in.split(",") if t.strip()]
                codes = fetch_universe_codes(tickers, n_exp, width)
            snaps = fetch_option_snapshots(codes)
            und_tickers = sorted({m.group(1) for m in (radar.CODE_RE.match(c) for c in codes) if m})
            unds = fetch_underlyings(und_tickers)

        if not snaps:
            st.error("No option snapshots returned.")
            st.stop()
        if not screen:   # fallback mode: OI change vs the last saved scan
            prev = _previous_oi()
            screen = [{"code": s["code"], "oi_day_chg": float(s.get("option_open_interest", 0) or 0) - prev[s["code"]]}
                      for s in snaps if s.get("code") in prev]

        df = radar.analyze(radar.build_table(snaps, unds, screen))
        bias = radar.underlying_bias(df)
        picks = radar.pick_contracts(df, bias)
        base = _save_scan("scan", df, bias, picks)
        st.session_state["radar"] = (df, bias, picks, base)

    if "radar" in st.session_state:
        df, bias, picks, base = st.session_state["radar"]
        n_sig = int(bias["signal"].str.contains("BUY").sum()) if not bias.empty else 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Contracts", len(df))
        m2.metric("Tickers", df["ticker"].nunique())
        m3.metric("Ticker signals", n_sig)
        m4.metric("Data date", str(df["data_date"].iloc[0]))
        st.caption("Saved as `{}_*.csv` — open **Radar Results** later to see how it performed.".format(os.path.basename(base)))

        st.subheader("Picks — best contract per signal")
        if picks.empty:
            st.info("No ticker has a clear signal right now. That is a valid result — no trade.")
        else:
            cols = ["signal", "code", "dte", "spot", "strike", "mid", "delta", "iv", "theta_pct", "spread_pct", "oi", "buyer_q"]
            st.dataframe(picks[cols].style.pipe(_color_signal)
                         .format({"spot": "${:.2f}", "strike": "${:.2f}", "mid": "${:.2f}", "delta": "{:.2f}",
                                  "iv": "{:.1f}", "theta_pct": "{:.1f}%", "spread_pct": "{:.1f}%",
                                  "oi": "{:,.0f}", "buyer_q": "{:.0f}"}),
                         use_container_width=True, hide_index=True)

        st.subheader("Ticker bias from option flow")
        st.dataframe(bias.style.pipe(_color_signal),
                     use_container_width=True, hide_index=True)

        st.subheader("Hot contracts — fresh positions (2+ days to expiry)")
        hot = df[df["dte"] >= 2].sort_values(["buildup_score", "volume"], ascending=False).head(30)
        st.dataframe(hot[["code", "type", "dte", "spot", "strike", "mid", "volume", "oi", "oi_chg", "vol_oi",
                          "excess_pct", "buildup", "buildup_tags", "delta", "iv", "theta_pct", "spread_pct", "buyer_q"]]
                     .round(2), use_container_width=True, hide_index=True)

        with st.expander("All contracts"):
            st.dataframe(df.round(3), use_container_width=True, hide_index=True)
        st.download_button("Download scan CSV", df.to_csv(index=False).encode(),
                           file_name=os.path.basename(base) + "_contracts.csv", mime="text/csv")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: RADAR RESULTS
# ════════════════════════════════════════════════════════════════════════════

elif page == "Radar Results":
    st.title("Radar Results")
    st.caption("Re-price a saved scan with live MooMoo data: did the readings predict the move?")

    files = sorted(_glob.glob(os.path.join(RADAR_DIR, "*_contracts.csv")), reverse=True)
    choice = st.selectbox("Saved scan", [os.path.basename(f) for f in files]) if files else None
    upload = st.file_uploader("…or upload a scan CSV", type="csv")
    if not choice and not upload:
        st.info("No saved scans yet — run **Options Radar** first.")
        st.stop()

    if st.button("Check performance now", type="primary"):
        base_df = pd.read_csv(upload) if upload else pd.read_csv(os.path.join(RADAR_DIR, choice))
        with st.spinner("Re-pricing {} contracts…".format(len(base_df))):
            snaps = fetch_option_snapshots(base_df["code"].tolist())
            unds = fetch_underlyings(sorted(base_df["ticker"].unique().tolist()))
        now = radar.build_table(snaps, unds)
        if now.empty:
            st.error("No live data returned.")
            st.stop()
        m, hit = radar.track(base_df, now)

        k1, k2, k3 = st.columns(3)
        k1.metric("Contracts re-priced", len(m))
        k2.metric("Avg option return", "{:+.1f}%".format(m["opt_ret_pct"].mean()))
        k3.metric("Winners", "{}/{}".format(int((m["opt_ret_pct"] > 0).sum()), len(m)))

        st.subheader("Did each buildup reading predict the stock? (2+ DTE)")
        if hit.empty:
            st.info("No directional readings in this scan.")
        else:
            st.dataframe(hit, use_container_width=True, hide_index=True)
            st.caption("Hit rate above 0.5 on one day is noise. Look for readings that stay above 0.5 across many scans.")

        if not choice:
            bias_path = picks_path = ""
        else:
            bias_path = os.path.join(RADAR_DIR, choice.replace("_contracts.csv", "_bias.csv"))
            picks_path = os.path.join(RADAR_DIR, choice.replace("_contracts.csv", "_picks.csv"))
        if bias_path and os.path.exists(bias_path):
            b = pd.read_csv(bias_path)
            b = b[b["signal"].str.contains("BUY")]
            if not b.empty:
                spot_now = m.groupby("ticker")["spot_now"].first()
                b["spot_now"] = b["ticker"].map(spot_now)
                b["stock_ret_pct"] = (b["spot_now"] - b["spot"]) / b["spot"] * 100
                b["signal_right"] = [("CALL" in s and r > 0) or ("PUT" in s and r < 0)
                                     for s, r in zip(b["signal"], b["stock_ret_pct"])]
                st.subheader("Ticker signals")
                st.dataframe(b[["ticker", "signal", "spot", "spot_now", "stock_ret_pct", "signal_right"]].round(2),
                             use_container_width=True, hide_index=True)
        if picks_path and os.path.exists(picks_path) and os.path.getsize(picks_path) > 5:
            p = pd.read_csv(picks_path)[["code", "signal"]].merge(
                m[["code", "mid_then", "mid_now", "opt_ret_pct"]], on="code")
            st.subheader("Picked contracts")
            st.dataframe(p.round(2), use_container_width=True, hide_index=True)

        cols = ["code", "type", "dte", "buildup", "spot_then", "spot_now", "spot_ret_pct", "mid_then", "mid_now", "opt_ret_pct"]
        b1, b2 = st.columns(2)
        b1.markdown("**Best 10**")
        b1.dataframe(m.sort_values("opt_ret_pct", ascending=False)[cols].head(10).round(2), hide_index=True)
        b2.markdown("**Worst 10**")
        b2.dataframe(m.sort_values("opt_ret_pct")[cols].head(10).round(2), hide_index=True)
