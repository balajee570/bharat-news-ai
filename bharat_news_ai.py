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
        st.error("TAVILY_API_KEY missing from secrets.toml")
        return [], []

    client = TavilyClient(api_key=key)

    # Call 1 — General news
    with st.spinner("Fetching national, international, finance, sports news…"):
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
            st.error(f"Search error: {e}")
            general = []

    # Call 2 — Regional
    with st.spinner("Fetching Bihar, Samastipur, Rosera news…"):
        try:
            r2 = client.search(
                query="Bihar news Samastipur Rosera Patna today latest",
                search_depth="advanced",
                max_results=10,
                days=3
            )
            regional = r2.get("results", [])
        except Exception as e:
            st.error(f"Regional search error: {e}")
            regional = []

    return general, regional


def categorise_general(articles):
    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
    }
    for a in articles:
        t = (
            (a.get("title",   "") or "") + " " +
            (a.get("content", "") or "")
        ).lower()

        if any(k in t for k in ["cricket", "ipl", "match", "score", "wicket",
                                  "football", "tennis", "sports", "player", "team"]):
            cats["sports"].append(a)
        elif any(k in t for k in ["nse", "bse", "sensex", "nifty", "stock",
                                   "market", "rupee", "gdp", "economy", "trade",
                                   "finance", "budget", "inflation"]):
            cats["finance"].append(a)
        elif any(k in t for k in ["world", "global", "usa", "us ", "china",
                                   "russia", "europe", "uk ", "pakistan",
                                   "international", "war", "ukraine", "nato"]):
            cats["international"].append(a)
        else:
            cats["national"].append(a)
    return cats


def categorise_regional(articles):
    cats = {
        "bihar":          [],
        "samastipur":     [],
        "rosera":         [],
        "other_regional": [],
    }
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
        elif "bihar" in t or "patna" in t:
            cats["bihar"].append(a)
        else:
            cats["other_regional"].append(a)

    return {k: v for k, v in cats.items() if v}


def render_articles(articles, max_n=6):
    if not articles:
        st.caption("No articles available right now.")
        return

    for a in articles[:max_n]:
        title   = (a.get("title",   "") or "").strip()
        content = (a.get("content", "") or "")[:250].strip()
        url     = (a.get("url",     "") or "").strip()
        source  = (a.get("source",  "") or "").strip()
        pub     = (a.get("published_date", "") or "")

        date_str = ""
        if pub:
            try:
                d = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                date_str = d.strftime("%d %b %Y")
            except:
                date_str = str(pub)[:10]

        with st.container(border=True):
            meta = []
            if source:   meta.append(source.upper())
            if date_str: meta.append(date_str)
            if meta:
                st.caption(" · ".join(meta))

            st.markdown(f"**{title}**")
            if content:
                st.write(content)
            if url:
                st.markdown(f"[Read full article ↗]({url})")


def insight_button(articles, label, key):
    if not get_key("SARVAM_API_KEY"):
        return
    if st.button("✦ Get AI Insight", key=key):
        lines = "\n".join(
            f"- {(a.get('title','') or '')}"
            for a in articles[:8]
        )
        with st.spinner("Generating insight…"):
            result = sarvam(
                f"Summarise these {label} news headlines in 2-3 sentences. "
                f"Be specific and factual.\n\n{lines}"
            )
        if result:
            st.info(f"✦ {result}")


# ── Header ────────────────────────────────────────────────────────
st.markdown("""
<div class="header-box">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Real-time news · AI insights · Bihar & India</p>
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
        f"  ·  2 search credits per refresh"
    )

st.divider()

if not fetch_btn:
    st.info(
        "Click **Refresh News** to load today's headlines.\n\n"
        "**Sections:** National · International · Finance · "
        "Sports · Bihar · Samastipur · Rosera · Word Intelligence\n\n"
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

gen_cats = categorise_general(general_raw)
reg_cats = categorise_regional(regional_raw)

# ── Stats ─────────────────────────────────────────────────────────
total = len(general_raw) + len(regional_raw)
c1, c2, c3, c4, c5, c6 = st.columns(6)

for col, emoji, label, count in [
    (c1, "🏠", "National",       len(gen_cats.get("national",     []))),
    (c2, "🌍", "International",  len(gen_cats.get("international", []))),
    (c3, "💰", "Finance",        len(gen_cats.get("finance",       []))),
    (c4, "⚽", "Sports",         len(gen_cats.get("sports",        []))),
    (c5, "📍", "Bihar/Regional", len(regional_raw)),
    (c6, "📰", "Total",          total),
]:
    with col:
        with st.container(border=True):
            st.metric(label=f"{emoji} {label}", value=count)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Bihar & Regional",
    "📚 Word Intelligence"
])

with tab1:
    st.subheader("🏠 National News")
    arts = gen_cats.get("national", [])
    insight_button(arts, "India national", "ins_national")
    render_articles(arts)

with tab2:
    st.subheader("🌍 International News")
    arts = gen_cats.get("international", [])
    insight_button(arts, "world international", "ins_intl")
    render_articles(arts)

with tab3:
    st.subheader("💰 Finance & Markets")
    arts = gen_cats.get("finance", [])
    insight_button(arts, "India finance and stock market", "ins_fin")
    render_articles(arts)

with tab4:
    st.subheader("⚽ Sports")
    arts = gen_cats.get("sports", [])
    insight_button(arts, "India sports and cricket", "ins_sports")
    render_articles(arts)

with tab5:
    st.subheader("📍 Bihar & Regional News")

    bihar  = reg_cats.get("bihar",      [])
    sams   = reg_cats.get("samastipur", [])
    rosera = reg_cats.get("rosera",     [])

    if bihar:
        st.markdown("### Bihar")
        insight_button(bihar, "Bihar", "ins_bihar")
        render_articles(bihar)
        st.divider()

    if sams:
        st.markdown("### Samastipur")
        render_articles(sams)
        st.divider()

    if rosera:
        st.markdown("### Rosera")
        render_articles(rosera)

    if not any([bihar, sams, rosera]):
        st.info(
            "No hyper-local results found today. "
            "Try again later or check Bihar tab for state news."
        )

with tab6:
    st.subheader("📚 Word Intelligence")
    st.caption(
        "AI picks 10 difficult words from today's "
        "headlines and explains them."
    )

    if not get_key("SARVAM_API_KEY"):
        st.warning("Add SARVAM_API_KEY to secrets.toml for Word Intelligence.")
    else:
        if st.button("✦ Analyse Words from Today's News", type="primary"):
            all_arts = general_raw + regional_raw
            combined = " ".join(
                f"{(a.get('title','') or '')} "
                f"{(a.get('content','') or '')[:150]}"
                for a in all_arts[:15]
            )[:2500]

            with st.spinner("Extracting words…"):
                result = sarvam(
                    f"Extract exactly 10 difficult English words from this "
                    f"news text. Return ONLY a valid JSON array, "
                    f"no markdown, no explanation:\n"
                    f'[{{"word":"...","meaning":"...","usage":"...",'
                    f'"description":"..."}}]\n\n'
                    f"Text: {combined}"
                )

            if result:
                result = re.sub(r"```json|```", "", result).strip()
                try:
                    m = re.search(r'\[.*\]', result, re.DOTALL)
                    if m:
                        words = json.loads(m.group())
                        for i, w in enumerate(words[:10], 1):
                            with st.container(border=True):
                                st.markdown(
                                    f"**#{i} {w.get('word','').upper()}**"
                                )
                                st.write(
                                    f"📖 **Meaning:** {w.get('meaning','')}"
                                )
                                st.write(
                                    f"✏️ **Usage:** _{w.get('usage','')}_"
                                )
                                st.caption(
                                    f"💡 {w.get('description','')}"
                                )
                    else:
                        st.warning("Could not parse word list. Try again.")
                except json.JSONDecodeError:
                    st.warning("Parse failed. Try again.")
            else:
                st.warning("No response. Check API key or try again.")

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · 2 credits/refresh"
)
