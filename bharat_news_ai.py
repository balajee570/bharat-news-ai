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


def sarvam(prompt):
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
                "temperature": 0.2
            },
            timeout=45
        )
        if resp.status_code == 200:
            c = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )
            return c.strip() if c else None
        return None
    except:
        return None


def fetch_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        st.error("TAVILY_API_KEY missing.")
        return [], []

    client = TavilyClient(api_key=key)
    general, regional = [], []

    with st.spinner("Fetching news…"):
        try:
            r1 = client.search(
                query=(
                    "India news today national international "
                    "stock market NSE BSE cricket IPL sports"
                ),
                search_depth="advanced",
                max_results=20,
                days=1
            )
            general = r1.get("results", [])
        except Exception as e:
            st.error(f"Error: {e}")

    with st.spinner("Fetching Bihar & regional news…"):
        try:
            r2 = client.search(
                query="Bihar Samastipur Rosera Patna news today",
                search_depth="advanced",
                max_results=10,
                days=3
            )
            regional = r2.get("results", [])
        except Exception as e:
            st.error(f"Error: {e}")

    return general, regional


def categorise(articles):
    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
    }

    SPORTS = [
        "cricket", "ipl", "wicket", "batting", "bowling",
        "odi", "t20", "icc", "bcci", "football", "fifa",
        "tennis", "badminton", "hockey", "kabaddi", "chess",
        "olympics", "sports", "stadium", "tournament", "trophy",
        "medal", "coach", "squad", "innings", "run chase"
    ]
    FINANCE = [
        "nse", "bse", "sensex", "nifty", "stock", "share price",
        "mutual fund", "rupee", "gdp", "finance", "budget",
        "inflation", "rbi", "interest rate", "investment",
        "ipo", "sebi", "fiscal", "revenue", "profit",
        "quarterly results", "earnings", "forex"
    ]
    INTL = [
        "world", "global", "usa", "united states", "china",
        "russia", "europe", "uk ", "united kingdom", "pakistan",
        "international", "war", "ukraine", "nato", "israel",
        "gaza", "un ", "g20", "imf", "world bank", "foreign",
        "diplomat", "sanctions"
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
    """Comprehensive AI summary of the category."""
    if not articles or not get_key("SARVAM_API_KEY"):
        return None

    combined = "\n\n".join(
        f"Headline: {(a.get('title','') or '').strip()}\n"
        f"Details: {(a.get('content','') or '')[:250].strip()}"
        for a in articles[:8]
    )

    prompt = (
        f"You are a senior news editor. Write a comprehensive news brief "
        f"for the {label} section based on these articles.\n\n"
        f"Format:\n"
        f"• Write 4-6 bullet points\n"
        f"• Each bullet covers one distinct story in 1-2 clear sentences\n"
        f"• Include key facts, numbers, names where available\n"
        f"• Be specific and informative — not vague\n"
        f"• Do not add section headings\n\n"
        f"Articles:\n{combined}"
    )
    return sarvam(prompt)


def get_words(articles):
    """Extract 10 difficult words from category content."""
    if not articles or not get_key("SARVAM_API_KEY"):
        return None

    combined = " ".join(
        f"{(a.get('title','') or '')} {(a.get('content','') or '')[:200]}"
        for a in articles[:8]
    )[:3000]

    prompt = (
        f"Extract exactly 10 difficult or important English words "
        f"from this news text. "
        f"Return ONLY a valid JSON array with no markdown:\n"
        f'[{{"word":"...","meaning":"...","usage":"...","description":"..."}}]\n\n'
        f"Text: {combined}"
    )

    result = sarvam(prompt)
    if not result:
        return None

    result = re.sub(r"```json|```", "", result).strip()
    try:
        m = re.search(r'\[.*\]', result, re.DOTALL)
        if m:
            return json.loads(m.group())[:10]
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
        return str(pub)[:10]


def render_section(articles, label):
    """
    Renders all three elements automatically:
    1. AI Summary
    2. News links
    3. Word intelligence
    No buttons — all generated on load.
    """
    if not articles:
        st.caption(f"No {label} news available right now.")
        return

    sv_key = get_key("SARVAM_API_KEY")

    # ── 1. AI Summary ─────────────────────────────────────────────
    st.markdown("#### 📰 News Brief")
    if sv_key:
        with st.spinner(f"Generating {label} summary…"):
            summary = get_summary(articles, label)
        if summary:
            st.info(summary)
        else:
            st.caption("Summary unavailable.")
    else:
        st.caption("Add SARVAM_API_KEY for AI summaries.")

    # ── 2. Reference links ────────────────────────────────────────
    st.markdown("#### 🔗 Sources")
    for a in articles[:8]:
        title    = (a.get("title", "") or "Untitled").strip()
        url      = (a.get("url",   "") or "").strip()
        pub      = a.get("published_date", "")
        time_str = format_time(pub)
        source   = (a.get("source", "") or "").strip().upper()

        meta = []
        if source:    meta.append(source)
        if time_str:  meta.append(time_str)
        meta_str = f"  ·  {' · '.join(meta)}" if meta else ""

        label_str = f"{title[:80]}{'…' if len(title)>80 else ''}{meta_str}"

        if url:
            st.markdown(f"- [{label_str}]({url})")
        else:
            st.markdown(f"- {label_str}")

    # ── 3. Word Intelligence ──────────────────────────────────────
    if sv_key:
        st.markdown("#### 📚 Word Intelligence")
        with st.spinner("Extracting words…"):
            words = get_words(articles)

        if words:
            cols = st.columns(2)
            for i, w in enumerate(words):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(
                            f"**{w.get('word','').upper()}**"
                        )
                        st.write(
                            f"📖 {w.get('meaning','')}"
                        )
                        st.caption(
                            f"✏️ _{w.get('usage','')}_"
                        )
        else:
            st.caption("Word intelligence unavailable.")


# ════════════════════════════════════════════════════════════════
# HEADER
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
        f"  ·  2 Tavily credits per refresh"
    )

st.divider()

if not fetch_btn:
    st.info(
        "Click **Refresh News** to load today's headlines.\n\n"
        "Each section auto-generates:\n"
        "- **AI News Brief** — comprehensive summary\n"
        "- **Source Links** — original articles\n"
        "- **Word Intelligence** — 10 difficult words explained\n\n"
        "**Credits:** 2 Tavily credits per refresh."
    )
    st.stop()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────
general_raw, regional_raw = fetch_news()

if not general_raw and not regional_raw:
    st.warning("No results. Check your API keys.")
    st.stop()

gen_cats = categorise(general_raw)
reg_cats = categorise_regional(regional_raw)

# ── Stats ─────────────────────────────────────────────────────────
total = len(general_raw) + len(regional_raw)
c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, emoji, lbl, count in [
    (c1, "🏠", "National",       len(gen_cats.get("national",     []))),
    (c2, "🌍", "International",  len(gen_cats.get("international", []))),
    (c3, "💰", "Finance",        len(gen_cats.get("finance",       []))),
    (c4, "⚽", "Sports",         len(gen_cats.get("sports",        []))),
    (c5, "📍", "Bihar/Regional", len(regional_raw)),
    (c6, "📰", "Total",          total),
]:
    with col:
        with st.container(border=True):
            st.metric(label=f"{emoji} {lbl}", value=count)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────
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
    render_section(gen_cats.get("sports", []), "India sports and cricket")

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
        st.info("No regional results today. Bihar news may appear in National tab.")

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · 2 credits/refresh"
)
