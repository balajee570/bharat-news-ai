import streamlit as st
import requests
import json
import re
from datetime import datetime, timezone, timedelta
from tavily import TavilyClient

IST = timezone(timedelta(hours=5, minutes=30))
def now_ist():
    return datetime.now(IST)

SARVAM_URL   = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_MODEL = "sarvam-105b"

st.set_page_config(
    page_title="Bharat News AI",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background: #f8f9fa; }
    .header-box {
        background: linear-gradient(135deg, #FF9933 0%, #1D3557 100%);
        color: white;
        padding: 1.8rem 2rem;
        border-radius: 14px;
        margin-bottom: 1.5rem;
    }
    .header-box h1 { font-size: 2rem; font-weight: 800; margin: 0; }
    .header-box p  { font-size: 0.9rem; opacity: 0.9; margin-top: 0.4rem; }
    #MainMenu, footer { visibility: hidden; }
    section[data-testid="stSidebar"] { display: none; }
</style>
""", unsafe_allow_html=True)


def get_key(k):
    try:
        return st.secrets[k]
    except:
        return ""


def sarvam_call(prompt):
    key = get_key("SARVAM_API_KEY")
    if not key:
        return None
    try:
        resp = requests.post(
            SARVAM_URL,
            headers={
                "api-subscription-key": key,
                "Content-Type": "application/json"
            },
            json={
                "model":       SARVAM_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  8192,
                "temperature": 0.1
            },
            timeout=60
        )
        if resp.status_code != 200:
            return None
        rj      = resp.json()
        choices = rj.get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content")
        return content.strip() if content else None
    except:
        return None


def fetch_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        st.error("TAVILY_API_KEY missing.")
        return [], []

    client   = TavilyClient(api_key=key)
    general  = []
    regional = []

    with st.spinner("Fetching news…"):
        queries = [
            "India national politics government news today",
            "India international world news today",
            "India NSE BSE stock market finance economy today",
            "India cricket IPL sports news today",
        ]
        seen = set()
        for q in queries:
            try:
                r = client.search(
                    query=q,
                    search_depth="advanced",
                    max_results=5,
                    days=1
                )
                for a in r.get("results", []):
                    u = a.get("url", "")
                    if u not in seen:
                        seen.add(u)
                        general.append(a)
            except:
                continue

    with st.spinner("Fetching Bihar & regional news…"):
        try:
            r2 = client.search(
                query="Bihar Patna Samastipur Rosera news today",
                search_depth="advanced",
                max_results=10,
                days=3
            )
            regional = r2.get("results", [])
        except:
            pass

    return general, regional


def categorise(articles):
    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
    }
    SPORTS = [
        "cricket", "ipl", "wicket", "batting", "bowling", "odi",
        "t20", "icc", "bcci", "football", "fifa", "tennis",
        "badminton", "hockey", "olympics", "sports", "tournament",
        "trophy", "medal", "squad", "innings"
    ]
    FINANCE = [
        "nse", "bse", "sensex", "nifty", "stock", "rupee", "gdp",
        "finance", "budget", "inflation", "rbi", "interest rate",
        "investment", "ipo", "sebi", "revenue", "profit",
        "earnings", "forex", "market"
    ]
    INTL = [
        "world", "global", "usa", "united states", "china", "russia",
        "europe", "uk ", "pakistan", "international", "war",
        "ukraine", "nato", "israel", "un ", "g20", "imf",
        "world bank", "foreign", "diplomat"
    ]
    for a in articles:
        t = (
            (a.get("title",   "") or "") + " " +
            (a.get("content", "") or "")
        ).lower()
        if any(k in t for k in SPORTS):
            cats["sports"].append(a)
        elif any(k in t for k in FINANCE):
            cats["finance"].append(a)
        elif any(k in t for k in INTL):
            cats["international"].append(a)
        else:
            cats["national"].append(a)
    return cats


def categorise_regional(articles):
    cats = {"rosera": [], "samastipur": [], "bihar": []}
    for a in articles:
        t = (
            (a.get("title",   "") or "") + " " +
            (a.get("content", "") or "") + " " +
            (a.get("url",     "") or "")
        ).lower()
        if "rosera" in t:
            cats["rosera"].append(a)
        elif "samastipur" in t:
            cats["samastipur"].append(a)
        else:
            cats["bihar"].append(a)
    return {k: v for k, v in cats.items() if v}


def get_summary(articles, label):
    """Short focused prompt — avoids finish_reason=length."""
    headlines = "\n".join(
        f"- {(a.get('title','') or '').strip()}: "
        f"{(a.get('content','') or '')[:150].strip()}"
        for a in articles[:7]
    )
    prompt = (
        f"Write 5 news bullet points for {label} section. "
        f"Each bullet = one story, 1-2 sentences, factual, specific. "
        f"Start each with •. No headings.\n\n{headlines}"
    )
    return sarvam_call(prompt)


def get_words(articles):
    """Short prompt for word extraction."""
    text = " ".join(
        (a.get("title", "") or "") + " " +
        (a.get("content", "") or "")[:150]
        for a in articles[:6]
    )[:2000]

    prompt = (
        f"Extract 8 difficult English words from this text. "
        f"Return ONLY JSON array, no markdown:\n"
        f'[{{"word":"...","meaning":"...","usage":"..."}}]\n\n'
        f"Text: {text}"
    )
    result = sarvam_call(prompt)
    if not result:
        return None
    clean = re.sub(r"```json|```", "", result).strip()
    try:
        m = re.search(r'\[.*?\]', clean, re.DOTALL)
        if m:
            return json.loads(m.group())[:8]
    except:
        pass
    return None


def format_time(pub):
    if not pub:
        return ""
    try:
        d     = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        d_ist = d.astimezone(IST)
        if d_ist.date() == now_ist().date():
            return d_ist.strftime("%I:%M %p IST")
        return d_ist.strftime("%d %b %Y")
    except:
        return ""


def render_section(articles, label):
    """
    Auto renders everything — no buttons.
    Order: Summary → Word Intelligence → Reference Links
    """
    if not articles:
        st.caption(f"No {label} news available right now.")
        return

    sv = get_key("SARVAM_API_KEY")

    # ── 1. AI Summary ─────────────────────────────────────────────
    st.markdown("**📰 Summary**")
    if sv:
        with st.spinner("Summarising…"):
            summary = get_summary(articles, label)
        if summary:
            st.write(summary)
        else:
            st.caption("Summary unavailable — check Sarvam key.")
    else:
        st.caption("Add SARVAM_API_KEY for AI summary.")

    st.markdown("")

    # ── 2. Word Intelligence ──────────────────────────────────────
    st.markdown("**📚 Word Intelligence**")
    if sv:
        with st.spinner("Extracting words…"):
            words = get_words(articles)
        if words:
            cols = st.columns(2)
            for i, w in enumerate(words):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{w.get('word','').upper()}**")
                        st.write(f"📖 {w.get('meaning','')}")
                        st.caption(f"✏️ _{w.get('usage','')}_")
        else:
            st.caption("Word intelligence unavailable.")
    else:
        st.caption("Add SARVAM_API_KEY for Word Intelligence.")

    st.markdown("")

    # ── 3. Reference Links ────────────────────────────────────────
    st.markdown("**🔗 References**")
    for a in articles[:8]:
        title    = (a.get("title",   "") or "Untitled").strip()
        url      = (a.get("url",     "") or "").strip()
        source   = (a.get("source",  "") or "").strip().upper()
        time_str = format_time(a.get("published_date", ""))

        meta     = " · ".join(filter(None, [source, time_str]))
        display  = f"{title[:70]}{'…' if len(title)>70 else ''}"
        if meta:
            display += f"  —  {meta}"

        if url:
            st.markdown(f"- [{display}]({url})")
        else:
            st.markdown(f"- {display}")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-box">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Real-time · AI curated · Bihar & India</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 4])
with col1:
    fetch_btn = st.button(
        "🔄 Refresh News",
        type="primary",
        use_container_width=True
    )
with col2:
    st.caption(
        f"🕐 {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
        f"  ·  5 Tavily credits per refresh"
    )

st.divider()

if not fetch_btn:
    st.info(
        "Click **Refresh News** to load today's headlines.\n\n"
        "Each tab auto-shows:\n"
        "- 📰 AI Summary\n"
        "- 📚 Word Intelligence\n"
        "- 🔗 Reference Links"
    )
    st.stop()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing.")
    st.stop()

general_raw, regional_raw = fetch_news()

if not general_raw and not regional_raw:
    st.warning("No results. Check Tavily key.")
    st.stop()

gen_cats = categorise(general_raw)
reg_cats = categorise_regional(regional_raw)
total    = len(general_raw) + len(regional_raw)

c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, emoji, lbl, count in [
    (c1, "🏠", "National",      len(gen_cats.get("national",     []))),
    (c2, "🌍", "Internatl",     len(gen_cats.get("international", []))),
    (c3, "💰", "Finance",       len(gen_cats.get("finance",       []))),
    (c4, "⚽", "Sports",        len(gen_cats.get("sports",        []))),
    (c5, "📍", "Bihar/Regional",len(regional_raw)),
    (c6, "📰", "Total",         total),
]:
    with col:
        with st.container(border=True):
            st.metric(label=f"{emoji} {lbl}", value=count)

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Bihar & Regional",
])

with tab1:
    st.subheader("🏠 National News")
    render_section(gen_cats.get("national", []), "India national")

with tab2:
    st.subheader("🌍 International News")
    render_section(gen_cats.get("international", []), "world international")

with tab3:
    st.subheader("💰 Finance & Markets")
    render_section(gen_cats.get("finance", []), "India finance and markets")

with tab4:
    st.subheader("⚽ Sports")
    render_section(gen_cats.get("sports", []), "India sports")

with tab5:
    st.subheader("📍 Bihar & Regional")

    bihar  = reg_cats.get("bihar",      [])
    sams   = reg_cats.get("samastipur", [])
    rosera = reg_cats.get("rosera",     [])

    if bihar:
        st.markdown("### Bihar")
        render_section(bihar, "Bihar")
        st.divider()
    if sams:
        st.markdown("### Samastipur")
        render_section(sams, "Samastipur")
        st.divider()
    if rosera:
        st.markdown("### Rosera")
        render_section(rosera, "Rosera")
    if not any([bihar, sams, rosera]):
        st.info("No regional results today.")

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
)
