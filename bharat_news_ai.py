import streamlit as st
import requests
import json
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from tavily import TavilyClient

IST = timezone(timedelta(hours=5, minutes=30))
def now_ist():
    return datetime.now(IST)

st.set_page_config(
    page_title="Bharat News AI",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background: #f8f9fa; }

    .header-main {
        background: linear-gradient(135deg, #FF9933 0%, #1D3557 100%);
        color: white;
        padding: 2rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .header-main h1 { font-size: 2.2rem; font-weight: 800; margin: 0; }
    .header-main p  { font-size: 0.95rem; opacity: 0.9; margin-top: 0.4rem; }

    .news-card {
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
        border-left: 4px solid #FF9933;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }
    .news-card:hover { box-shadow: 0 6px 20px rgba(0,0,0,0.1); }

    .news-title {
        font-size: 1rem;
        font-weight: 700;
        color: #1D3557;
        margin-bottom: 0.5rem;
        line-height: 1.4;
    }
    .news-source {
        font-size: 0.75rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    .news-snippet {
        font-size: 0.9rem;
        color: #444;
        line-height: 1.6;
    }
    .ai-insight {
        background: #f0fdf4;
        border-left: 3px solid #16a34a;
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 0.85rem;
        color: #166534;
        margin-bottom: 14px;
        line-height: 1.6;
    }
    .stat-box {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #FF9933;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .stat-number { font-size: 1.8rem; font-weight: 800; color: #FF9933; }
    .stat-label  { font-size: 0.8rem; color: #666; margin-top: 0.3rem; }

    .word-card {
        background: white;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
        border-left: 4px solid #138808;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .word-text    { font-size: 1.1rem; font-weight: 800; color: #138808; margin-bottom: 0.6rem; }
    .word-meaning { font-size: 0.9rem; color: #333; padding: 0.7rem; background: #f0f8f0; border-radius: 6px; margin-bottom: 0.5rem; }
    .word-usage   { font-size: 0.85rem; color: #555; font-style: italic; padding: 0.7rem; background: #fff9f0; border-radius: 6px; margin-bottom: 0.5rem; }
    .word-desc    { font-size: 0.85rem; color: #444; line-height: 1.6; }

    .empty-state  { text-align: center; padding: 2rem; color: #aaa; font-size: 0.95rem; }

    #MainMenu, footer { visibility: hidden; }
    section[data-testid="stSidebar"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ── Keys ──────────────────────────────────────────────────────────
def get_key(k):
    try:
        return st.secrets[k]
    except:
        return ""

TAVILY_KEY = get_key("TAVILY_API_KEY")
SARVAM_KEY = get_key("SARVAM_API_KEY")

SARVAM_URL   = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_MODEL = "sarvam-105b"


# ── Sarvam call — correct URL + correct auth ──────────────────────
def sarvam_call(prompt, max_tokens=8192):
    """
    Correct Sarvam-105b call.
    URL:  /v1/chat/completions  (not /chat/completion)
    Auth: api-subscription-key  (not Bearer)
    max_tokens: 8192            (reasoning model needs headroom)
    """
    if not SARVAM_KEY:
        return None
    try:
        resp = requests.post(
            SARVAM_URL,
            headers={
                "api-subscription-key": SARVAM_KEY,
                "Content-Type": "application/json"
            },
            json={
                "model":       SARVAM_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  max_tokens,
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


# ── Tavily search ─────────────────────────────────────────────────
def tavily_search(query, n=15, days=1):
    if not TAVILY_KEY:
        return []
    try:
        client = TavilyClient(api_key=TAVILY_KEY)
        res = client.search(
            query=query,
            search_depth="advanced",
            max_results=n,
            days=days
        )
        return res.get("results", [])
    except Exception as e:
        st.error(f"Search error: {e}")
        return []


# ── 4 Tavily calls — focused per section ─────────────────────────
def fetch_all_news():
    results = {}

    with st.spinner("Fetching national & international news…"):
        results["national"] = tavily_search(
            "India national news today government politics economy", n=10
        )
        results["international"] = tavily_search(
            "world international news today USA China Europe", n=10
        )

    with st.spinner("Fetching finance & sports…"):
        results["finance"] = tavily_search(
            "India stock market NSE BSE Sensex Nifty finance economy today", n=10
        )
        results["sports"] = tavily_search(
            "India cricket IPL sports today match result", n=10
        )

    with st.spinner("Fetching regional news — Bihar, Samastipur, Rosera…"):
        results["bihar"] = tavily_search(
            "Bihar news today Patna government", n=8, days=2
        )
        results["samastipur"] = tavily_search(
            "Samastipur news today Bihar", n=5, days=3
        )
        results["rosera"] = tavily_search(
            "Rosera news Samastipur Bihar", n=5, days=7
        )

    return results


# ── Category-level AI insight — 1 call per tab ───────────────────
def get_category_insight(articles, category_name):
    if not SARVAM_KEY or not articles:
        return None
    lines = "\n".join(
        f"- {a.get('title','')}: {(a.get('content','') or '')[:80]}"
        for a in articles[:8]
    )
    prompt = (
        f"These are today's top {category_name} news headlines.\n"
        f"{lines}\n\n"
        f"Write 2-3 sentences summarising the key developments. "
        f"Be specific and factual."
    )
    return sarvam_call(prompt)


# ── Word extraction ───────────────────────────────────────────────
def extract_words(all_articles):
    if not SARVAM_KEY:
        return None
    combined = " ".join(
        f"{a.get('title','')} {a.get('content','') or ''}"
        for a in all_articles[:12]
    )[:2000]

    prompt = (
        f"Extract 10 difficult English words from this news text. "
        f"Return ONLY a valid JSON array, no markdown:\n"
        f'[{{"word":"...","meaning":"...","usage":"...","description":"..."}}]\n\n'
        f"Text: {combined}"
    )
    result = sarvam_call(prompt, max_tokens=8192)
    if not result:
        return None
    try:
        m = re.search(r'\[.*\]', result, re.DOTALL)
        if m:
            return json.loads(m.group())
    except:
        pass
    return None


# ── Render news cards — pure Streamlit ───────────────────────────
def render_articles(articles, max_n=6):
    if not articles:
        st.markdown(
            '<div class="empty-state">No articles available right now.</div>',
            unsafe_allow_html=True
        )
        return
    for a in articles[:max_n]:
        title   = a.get("title",   "") or ""
        content = (a.get("content","") or "")[:250]
        url     = a.get("url",     "") or ""
        source  = a.get("source",  "") or ""
        pub     = a.get("published_date", "") or ""

        date_str = ""
        if pub:
            try:
                d = datetime.fromisoformat(pub.replace("Z","+00:00"))
                date_str = d.strftime("%d %b %Y")
            except:
                date_str = str(pub)[:10]

        with st.container():
            st.markdown(f"""
            <div class="news-card">
                <div class="news-source">
                    {source}{"  ·  " + date_str if date_str else ""}
                </div>
                <div class="news-title">{title}</div>
                <div class="news-snippet">{content}</div>
            </div>
            """, unsafe_allow_html=True)
            if url:
                st.markdown(
                    f"[Read full article ↗]({url})",
                    help=url
                )


# ════════════════════════════════════════════════════════════════
# MAIN UI
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-main">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Real-time news with AI insights · Bihar & India · 
    Powered by Sarvam-105B</p>
</div>
""", unsafe_allow_html=True)

col_refresh, col_time, col_max = st.columns([1, 3, 2])
with col_refresh:
    fetch_btn = st.button("🔄 Refresh News", type="primary", use_container_width=True)
with col_time:
    st.caption(f"🕐 {now_ist().strftime('%d %b %Y, %I:%M %p')} IST")
with col_max:
    max_articles = st.slider("Articles per section", 3, 8, 5)

st.divider()

if not fetch_btn:
    st.info("Click **Refresh News** to load the latest headlines.")
    st.stop()

if not TAVILY_KEY:
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────
news = fetch_all_news()

# ── Stats row ─────────────────────────────────────────────────────
total = sum(len(v) for v in news.values())
c1, c2, c3, c4, c5 = st.columns(5)
for col, label, key in [
    (c1, "🏠 National",      "national"),
    (c2, "🌍 International", "international"),
    (c3, "💰 Finance",       "finance"),
    (c4, "⚽ Sports",        "sports"),
    (c5, "📍 Regional",      "bihar"),
]:
    with col:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-number">{len(news.get(key,[]))}</div>
            <div class="stat-label">{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Regional",
    "📚 Word of the Day"
])

with tab1:
    st.subheader("🏠 National News")
    insight = get_category_insight(news.get("national",[]), "India national")
    if insight:
        st.markdown(f'<div class="ai-insight">✦ {insight}</div>', unsafe_allow_html=True)
    render_articles(news.get("national", []), max_articles)

with tab2:
    st.subheader("🌍 International News")
    insight = get_category_insight(news.get("international",[]), "world international")
    if insight:
        st.markdown(f'<div class="ai-insight">✦ {insight}</div>', unsafe_allow_html=True)
    render_articles(news.get("international", []), max_articles)

with tab3:
    st.subheader("💰 Finance & Markets")
    insight = get_category_insight(news.get("finance",[]), "India stock market and finance")
    if insight:
        st.markdown(f'<div class="ai-insight">✦ {insight}</div>', unsafe_allow_html=True)
    render_articles(news.get("finance", []), max_articles)

with tab4:
    st.subheader("⚽ Sports")
    insight = get_category_insight(news.get("sports",[]), "India sports and cricket")
    if insight:
        st.markdown(f'<div class="ai-insight">✦ {insight}</div>', unsafe_allow_html=True)
    render_articles(news.get("sports", []), max_articles)

with tab5:
    st.subheader("📍 Regional News")

    r1, r2, r3 = st.columns(3)

    with r1:
        st.markdown("### Bihar")
        render_articles(news.get("bihar", []), max_articles)

    with r2:
        st.markdown("### Samastipur")
        render_articles(news.get("samastipur", []), max_articles)

    with r3:
        st.markdown("### Rosera")
        render_articles(news.get("rosera", []), max_articles)

with tab6:
    st.subheader("📚 Difficult Words from Today's News")
    st.caption("AI picks 10 difficult words from today's headlines and explains them.")

    if st.button("✦ Analyse Words", type="primary"):
        all_articles = []
        for v in news.values():
            all_articles.extend(v)

        with st.spinner("Extracting words…"):
            words = extract_words(all_articles)

        if words:
            for i, w in enumerate(words[:10], 1):
                st.markdown(f"""
                <div class="word-card">
                    <div class="word-text">#{i} {w.get('word','')}</div>
                    <div class="word-meaning"><strong>Meaning:</strong> {w.get('meaning','')}</div>
                    <div class="word-usage"><strong>Usage:</strong> "{w.get('usage','')}"</div>
                    <div class="word-desc"><strong>Why it matters:</strong> {w.get('description','')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Could not extract words. Check Sarvam API key.")

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · Sarvam-105B · Tavily"
)
