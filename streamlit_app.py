"""
Subba US Options Analyzer — Streamlit Cloud app.
Real-time MooMoo data via gateway-free REST API (webapi.moomoo.com).
OAuth 2.1 + PKCE login — no FutuOpenD needed.

Setup (one-time):
  1. Go to https://open.moomoo.com → sign in → Developer → Create App
  2. Set redirect URI to your Streamlit app URL
  3. Copy your Client ID
  4. In Streamlit Cloud → App secrets, add:
       MOOMOO_CLIENT_ID = "your_client_id"
       REDIRECT_URI = "https://your-app.streamlit.app"
"""
import os
import time
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

# ── MooMoo OAuth + REST API constants ────────────────────────────────────────

MOOMOO_API       = "https://webapi.moomoo.com/api/v1.0"
AUTHORIZE_URL    = "https://webapi.moomoo.com/oauth2/authorize/confirm"
TOKEN_URL        = "https://webapi.moomoo.com/oauth2/token"
REGISTER_URL     = "https://webapi.moomoo.com/oauth2/register"

# ── OAuth config from Streamlit secrets ──────────────────────────────────────

def _secret(key: str, default: str = "") -> str:
    if hasattr(st, "secrets") and key in st.secrets:
        return str(st.secrets[key])
    return os.environ.get(key, default)


CLIENT_ID    = _secret("MOOMOO_CLIENT_ID")
REDIRECT_URI = _secret("REDIRECT_URI", "http://localhost:8501")


# ════════════════════════════════════════════════════════════════════════════
# OAUTH SETUP SCREEN (shown if no client_id configured)
# ════════════════════════════════════════════════════════════════════════════

if not CLIENT_ID:
    st.title("Subba US Options — Setup")
    st.error("**MOOMOO_CLIENT_ID** not configured in Streamlit secrets.")

    st.markdown("""
    ### One-time setup (takes ~2 minutes)

    **Step 1** — Register your app on MooMoo developer portal:
    1. Go to **[open.moomoo.com](https://open.moomoo.com)** and sign in with your MooMoo account
    2. Click **Developer** → **Create Application**
    3. Set the **Redirect URI** to your Streamlit app URL:
       ```
       https://stockanalyser-subba-us.streamlit.app
       ```
    4. Copy your **Client ID**

    **Step 2** — Add to Streamlit Cloud secrets:

    In your Streamlit app → **⋮ Menu** → **Settings** → **Secrets**, add:
    ```toml
    MOOMOO_CLIENT_ID = "paste_your_client_id_here"
    REDIRECT_URI = "https://stockanalyser-subba-us.streamlit.app"
    ```

    **Step 3** — Reopen the app → click **Login with MooMoo** → done!
    """)

    st.info("The MooMoo developer portal provides a Client ID for their gateway-free REST API — same concept as Kite Connect's API key.")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# OAUTH LOGIN  (pure server-side PKCE — no browser JS, no CORS issues)
# ════════════════════════════════════════════════════════════════════════════

import hashlib, base64, secrets as _secrets, urllib.parse


CLIENT_SECRET = _secret("MOOMOO_CLIENT_SECRET", "")


def _build_auth_url() -> str:
    if "oauth_state" not in st.session_state:
        st.session_state.oauth_state = _secrets.token_urlsafe(16)
    params = {
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "state":         st.session_state.oauth_state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str) -> bool:
    """Exchange auth code for token (form-encoded, server-side)."""
    payload = {
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": REDIRECT_URI,
        "client_id":    CLIENT_ID,
    }
    if CLIENT_SECRET:
        payload["client_secret"] = CLIENT_SECRET

    resp = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if resp.ok:
        td = resp.json()
        st.session_state.token = td
        st.session_state.token_expires_at = time.time() + td.get("expires_in", 7200) - 60
        return True
    st.error(f"Token exchange failed ({resp.status_code})")
    with st.expander("Error detail"):
        st.code(resp.text)
    return False


if "token" not in st.session_state:
    qp = st.query_params
    if "error" in qp:
        st.error(f"MooMoo returned error: **{qp['error']}** — {qp.get('error_description', '')}")
        if st.button("Try again"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    if "code" in qp:
        with st.spinner("Logging in…"):
            ok = _exchange_code(qp["code"])
        if ok:
            st.query_params.clear()
            st.rerun()
        else:
            if st.button("Try again"):
                st.query_params.clear()
                st.rerun()
        st.stop()

    st.title("Subba US Options")
    st.markdown("Real-time MooMoo data — **no local software needed**.")
    st.divider()
    auth_url = _build_auth_url()
    st.link_button("Login with MooMoo 📈", auth_url, type="primary")

    st.stop()


# ── Token refresh ─────────────────────────────────────────────────────────────

def _refresh_token():
    rt = st.session_state.token.get("refresh_token")
    if not rt:
        return
    payload = {"grant_type": "refresh_token", "refresh_token": rt, "client_id": CLIENT_ID}
    if CLIENT_SECRET:
        payload["client_secret"] = CLIENT_SECRET
    resp = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.ok:
        td = resp.json()
        st.session_state.token = td
        st.session_state.token_expires_at = time.time() + td.get("expires_in", 7200) - 60


if time.time() > st.session_state.get("token_expires_at", float("inf")):
    _refresh_token()

ACCESS_TOKEN = st.session_state.token.get("access_token", "")


def _auth_headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


# ════════════════════════════════════════════════════════════════════════════
# REST API HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _get(path: str, params: dict = None, timeout: int = 30):
    try:
        r = requests.get(
            f"{MOOMOO_API}{path}",
            headers=_auth_headers(),
            params=params,
            timeout=timeout,
        )
        if r.status_code == 401:
            st.session_state.pop("token", None)
            st.error("Session expired. Please log in again.")
            st.stop()
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        st.error(f"API error {path}: {e}")
        return None


def us(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if t.startswith("US.") else f"US.{t}"


# ── Cached data functions ─────────────────────────────────────────────────────

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
    """Returns raw chain data from REST API."""
    return _get("/quote/option-chain", {
        "code": us(ticker),
        "start_strike_time": expiry,
        "end_strike_time": expiry,
    }, timeout=60)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_option_snapshot(option_codes_csv: str):
    return _get("/quote/market-snapshot", {"code_list": option_codes_csv})


@st.cache_data(ttl=120, show_spinner=False)
def fetch_acc_info():
    return _get("/account/acc-info")


@st.cache_data(ttl=120, show_spinner=False)
def fetch_positions():
    return _get("/account/position-list")


def _parse_chain_rows(chain_data, expiry: str):
    """Parse REST API option chain response into list of dicts."""
    if not chain_data or "data" not in chain_data:
        return []
    rows = []
    option_list = chain_data["data"].get("option_chain", [])
    for item in option_list:
        for opt_type in ["call", "put"]:
            opts = item.get(opt_type, [])
            if not isinstance(opts, list):
                opts = [opts] if opts else []
            for opt in opts:
                if not opt:
                    continue
                rows.append({
                    "code": opt.get("code", ""),
                    "strike": float(opt.get("strike_price", 0)),
                    "option_type": "CALL" if opt_type == "call" else "PUT",
                    "last": float(opt.get("last_price", 0)),
                    "bid":  float(opt.get("bid_price", 0)),
                    "ask":  float(opt.get("ask_price", 0)),
                    "open_interest": int(opt.get("open_interest", 0)),
                    "volume": int(opt.get("volume", 0)),
                    "iv":    float(opt.get("implied_volatility", 0)),
                    "delta": float(opt.get("delta", 0)),
                    "gamma": float(opt.get("gamma", 0)),
                    "theta": float(opt.get("theta", 0)),
                })
    return rows


def _spot_from_snapshot(snap_data, ticker: str) -> float:
    if not snap_data or "data" not in snap_data:
        return 0.0
    for item in snap_data.get("data", {}).get("snapshot_list", []):
        if us(ticker) in item.get("code", ""):
            return float(item.get("last_price", 0))
    return 0.0


# ════════════════════════════════════════════════════════════════════════════
# ANALYSIS HELPERS
# ════════════════════════════════════════════════════════════════════════════

def calc_pcr(rows):
    ce = sum(r.get("open_interest", 0) for r in rows if r["option_type"] == "CALL")
    pe = sum(r.get("open_interest", 0) for r in rows if r["option_type"] == "PUT")
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
        by_s[s]["ce" if r["option_type"] == "CALL" else "pe"] += r.get("open_interest", 0)
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
    score = 0
    details = []

    if pcr >= 1.3:   score += 2; details.append(("PCR", f"{pcr:.2f}", "Bullish 🟢", "Heavy put writing"))
    elif pcr >= 1.0: score += 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bullish 🟡", "More puts"))
    elif pcr <= 0.7: score -= 2; details.append(("PCR", f"{pcr:.2f}", "Bearish 🔴", "Heavy call writing"))
    elif pcr < 1.0:  score -= 1; details.append(("PCR", f"{pcr:.2f}", "Mildly Bearish 🟡", "More calls"))
    else:            details.append(("PCR", f"{pcr:.2f}", "Neutral ⚪", "Balanced OI"))

    mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0
    if mp_pct > 1.0:    score -= 2; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Bearish 🔴", "Spot above MP"))
    elif mp_pct > 0.3:  score -= 1; details.append(("Max Pain", f"+{mp_pct:.1f}%", "Mildly Bearish 🟡", ""))
    elif mp_pct < -1.0: score += 2; details.append(("Max Pain", f"{mp_pct:.1f}%", "Bullish 🟢", "Spot below MP"))
    elif mp_pct < -0.3: score += 1; details.append(("Max Pain", f"{mp_pct:.1f}%", "Mildly Bullish 🟡", ""))
    else:               details.append(("Max Pain", f"{mp_pct:.1f}%", "Neutral ⚪", "Spot near MP"))

    calls = sorted([r for r in rows if r["option_type"] == "CALL"], key=lambda x: x["strike"])
    puts  = sorted([r for r in rows if r["option_type"] == "PUT"],  key=lambda x: x["strike"])
    max_ce_oi = max((r.get("open_interest", 0) for r in calls), default=0)
    max_pe_oi = max((r.get("open_interest", 0) for r in puts),  default=0)
    ce_wall = next((r["strike"] for r in calls if r.get("open_interest", 0) == max_ce_oi), 0)
    pe_wall = next((r["strike"] for r in puts  if r.get("open_interest", 0) == max_pe_oi), 0)
    if spot > ce_wall > 0:
        score += 1; details.append(("OI Walls", f"Spot > CE wall ${ce_wall:.0f}", "Bullish 🟢", "Resistance cleared"))
    elif 0 < spot < pe_wall:
        score -= 1; details.append(("OI Walls", f"Spot < PE wall ${pe_wall:.0f}", "Bearish 🔴", "Support broken"))
    else:
        details.append(("OI Walls", f"CE ${ce_wall:.0f} | PE ${pe_wall:.0f}", "Neutral ⚪", "Spot between walls"))

    if   score >=  4: sig = "STRONG BUY CALL 📈"
    elif score >=  2: sig = "BUY CALL 📈"
    elif score <= -4: sig = "STRONG BUY PUT 📉"
    elif score <= -2: sig = "BUY PUT 📉"
    else:             sig = "NEUTRAL — WAIT ⚖️"

    return sig, score, details, ce_wall, pe_wall


def sig_color(sig: str) -> str:
    s = sig.upper()
    if "STRONG BUY CALL" in s: return "#22c55e"
    if "BUY CALL" in s:        return "#86efac"
    if "STRONG BUY PUT" in s:  return "#ef4444"
    if "BUY PUT" in s:         return "#fca5a5"
    return "#94a3b8"


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📈 Subba US Options")
    st.markdown("<span style='color:#22c55e;font-size:0.8rem'>● Logged in — MooMoo REST API</span>", unsafe_allow_html=True)
    st.caption("Gateway-free · Real-time data")

    page = st.radio(
        "Navigate",
        ["Dashboard", "Options Chain", "OI Signal", "Expiry Analyzer", "OI Scanner", "Smart Signal"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("Logout"):
        for k in ["token", "token_expires_at", "pkce_verifier", "pkce_challenge", "oauth_state"]:
            st.session_state.pop(k, None)
        st.rerun()


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
        cols = st.columns(4)
        for i, item in enumerate(snap_list):
            code = str(item.get("code", "")).replace("US.", "")
            last = float(item.get("last_price", 0))
            chg  = float(item.get("change_rate", 0))
            cols[i % 4].metric(code, f"${last:.2f}", delta=f"{chg:+.2f}%", delta_color="normal")
    else:
        st.info("No quote data — check API connection.")

    st.divider()
    st.subheader("Account")
    c1, c2 = st.columns(2)
    with c1:
        funds = fetch_acc_info()
        if funds and "data" in funds:
            d = funds["data"]
            st.metric("Cash",         f"${float(d.get('cash', 0)):,.2f}")
            st.metric("Market Value", f"${float(d.get('market_val', 0)):,.2f}")
            st.metric("Total Assets", f"${float(d.get('total_assets', 0)):,.2f}")
        else:
            st.caption("Account data unavailable.")
    with c2:
        pos = fetch_positions()
        if pos and "data" in pos:
            rows = pos["data"].get("position_list", [])
            if rows:
                df = pd.DataFrame(rows)
                show = [c for c in ["code","qty","cost_price","market_val","unrealized_pl"] if c in df.columns]
                st.dataframe(df[show].style.format({"cost_price":"${:.2f}","market_val":"${:.2f}","unrealized_pl":"${:.2f}"}),
                             use_container_width=True)
            else:
                st.caption("No open positions.")
        else:
            st.caption("Positions unavailable.")


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

    rows  = _parse_chain_rows(chain_raw, expiry)
    spot  = _spot_from_snapshot(snap_raw, ticker)

    if not rows:
        st.info("No chain data returned. The endpoint format may need adjustment — check MooMoo docs at open.moomoo.com.")
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
            st.dataframe(calls_df[cols].style.format({k:v for k,v in fmt.items() if k in cols}), use_container_width=True)
    with tab_p:
        if not puts_df.empty:
            cols = [c for c in disp if c in puts_df.columns]
            st.dataframe(puts_df[cols].style.format({k:v for k,v in fmt.items() if k in cols}), use_container_width=True)


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
        col = sig_color(signal)
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
        m1.metric("PCR", f"{pcr:.2f}")
        m2.metric("Max Pain", f"${max_pain:.2f}")
        m3.metric("MP Dist%", f"{mp_pct:+.1f}%")
        m4.metric("CE Wall", f"${ce_wall:.0f}")
        m5.metric("PE Wall", f"${pe_wall:.0f}")

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
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI", marker_color="#ef4444")
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot", line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike (ATM ±20)",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=320)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Signal Breakdown")
        st.dataframe(pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]), use_container_width=True)

        # Trade recommendation
        is_call   = "CALL" in signal
        is_strong = "STRONG" in signal
        is_neutral = "NEUTRAL" in signal
        if not is_neutral:
            gaps = [b - a for a, b in zip(all_strikes, all_strikes[1:])]
            gap = min(gaps) if gaps else 1.0
            rec_strike = atm if is_strong else (atm + gap if is_call else atm - gap)
            otype = "CALL" if is_call else "PUT"
            cands = [r for r in rows if r["option_type"] == otype and abs(r["strike"] - rec_strike) < gap * 0.6]
            ltp = cands[0]["last"] if cands else 0
            actual_strike = cands[0]["strike"] if cands else rec_strike
            sl = round(ltp * 0.65, 2)
            target = round(ltp * 1.65, 2)
            rr = round((target - ltp) / (ltp - sl), 1) if ltp > sl else 0
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
        col = sig_color(signal)
        mp_pct = (spot - max_pain) / max_pain * 100 if max_pain else 0

        if mp_pct < -1.5 and pcr > 1.1:
            st.success("🚀 ROCKET UP — Spot well below Max Pain with bullish OI.")
        elif mp_pct > 1.5 and pcr < 0.9:
            st.error("💣 ROCKET DOWN — Spot well above Max Pain with bearish OI.")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Spot", f"${spot:.2f}")
        m2.metric("Max Pain", f"${max_pain:.2f}")
        m3.metric("PCR", f"{pcr:.2f}")
        m4.metric("MP Dist%", f"{mp_pct:+.1f}%")
        m5.metric("CE Wall", f"${ce_wall:.0f}")
        m6.metric("PE Wall", f"${pe_wall:.0f}")

        st.markdown(
            f"""<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 18px;margin:.6rem 0">
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
                fig.add_bar(x=p_df["strike"], y=p_df["open_interest"], name="Puts OI", marker_color="#ef4444")
            fig.add_vline(x=spot, line_dash="dash", line_color="#f59e0b", annotation_text="Spot")
            fig.add_vline(x=max_pain, line_dash="dot", line_color="#a855f7", annotation_text="MaxPain")
            fig.update_layout(barmode="group", title="OI by Strike",
                              paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=300)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Signal Factors")
        st.dataframe(pd.DataFrame(details, columns=["Indicator","Value","Verdict","Explanation"]), use_container_width=True)


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
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, tk in enumerate(tickers_list):
            status.caption(f"Scanning {tk}… ({i+1}/{len(tickers_list)})")
            exps = fetch_expirations(tk)
            if not exps or offset >= len(exps):
                progress.progress((i+1)/len(tickers_list))
                continue
            expiry = exps[offset]
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

        status.empty()
        progress.empty()

        if not results:
            st.warning("No results.")
        else:
            results.sort(key=lambda r: abs(r["score"]), reverse=True)
            st.success(f"Scanned {len(tickers_list)} tickers · {len(results)} results")
            df = pd.DataFrame(results)
            fig = px.bar(df, x="ticker", y="score", color="score",
                         color_continuous_scale=["#ef4444","#94a3b8","#22c55e"],
                         range_color=[-6,6], title="OI Score by Ticker")
            fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b",
                              font_color="#94a3b8", height=240, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            display = df.copy()
            display["signal"] = display["signal"].str.replace(r" 📈| 📉| ⚖️","", regex=True)
            st.dataframe(display.rename(columns={"ce_wall":"CE Wall","pe_wall":"PE Wall"})
                         .style.format({"spot":"${:.2f}","pcr":"{:.2f}","max_pain":"${:.2f}",
                                        "mp_dist_pct":"{:+.1f}%","CE Wall":"${:.0f}","PE Wall":"${:.0f}"}),
                         use_container_width=True)


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
                ce_oi  = sum(r.get("open_interest",0) for r in rows if r["option_type"]=="CALL")
                pe_oi  = sum(r.get("open_interest",0) for r in rows if r["option_type"]=="PUT")
                results.append({"expiry":expiry,"pcr":pcr,"max_pain":max_pain,"signal":sig,
                                 "score":score,"ce_wall":ce_wall,"pe_wall":pe_wall,
                                 "mp_dist_pct":mp_pct,"ce_oi_k":ce_oi/1000,"pe_oi_k":pe_oi/1000})
            progress.progress((i+1)/len(scan_exps))

        status.empty()
        progress.empty()

        if not results:
            st.warning("No data returned.")
            st.stop()

        best = max(results, key=lambda r: abs(r["score"]))
        col = sig_color(best["signal"])
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
