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
        choices = resp.json().get("choices", [])
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content")
        return content.strip() if content else None
    except:
        return None


# ── 2 Tavily calls only ───────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        return {}

    client = TavilyClient(api_key=key)

    breaking_domains = [
        "ndtv.com", "thehindu.com", "hindustantimes.com",
        "timesofindia.com", "indianexpress.com", "livemint.com",
        "news18.com", "abplive.com", "zeenews.india.com",
        "aninews.in", "reuters.com", "moneycontrol.com",
        "economictimes.indiatimes.com", "espncricinfo.com",
        "cricbuzz.com", "bbc.com",
    ]
    bihar_domains = [
        "bhaskar.com", "jagran.com", "livehindustan.com",
        "ndtv.com", "thehindu.com", "timesofindia.com",
        "news18.com", "abplive.com",
    ]

    general  = []
    regional = []

    # ── Call 1 — all general categories ──────────────────────────
    try:
        r1 = client.search(
            query=(
                "India breaking news right now "
                "national politics government finance stock market "
                "cricket IPL sports international world"
            ),
            search_depth="advanced",
            max_results=20,
            days=1,
            include_domains=breaking_domains
        )
        general = [
            a for a in r1.get("results", [])
            if not any(
                x in (a.get("url","") or "").lower()
                for x in ["google.com","yahoo.com","msn.com","apple.news"]
            )
        ]
    except Exception as e:
        pass

    # ── Call 2 — Bihar + regional ─────────────────────────────────
    try:
        r2 = client.search(
            query=(
                "Bihar Patna Samastipur Rosera "
                "breaking news right now today"
            ),
            search_depth="advanced",
            max_results=10,
            days=3,
            include_domains=bihar_domains
        )
        regional = r2.get("results", [])
    except Exception as e:
        pass

    # ── Categorise general ────────────────────────────────────────
    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
        "bihar":         [],
        "samastipur":    [],
        "rosera":        [],
    }

    SPORTS  = [
        "cricket","ipl","wicket","batting","bowling","odi","t20",
        "icc","bcci","football","fifa","tennis","badminton",
        "hockey","olympics","sports","tournament","medal","squad",
        "innings","match","score","player"
    ]
    FINANCE = [
        "nse","bse","sensex","nifty","stock","rupee","gdp",
        "finance","budget","inflation","rbi","interest rate",
        "investment","ipo","sebi","revenue","profit","earnings",
        "forex","market","economy","crude oil","gold price"
    ]
    INTL    = [
        "world","global","usa","united states","china","russia",
        "europe","uk ","pakistan","international","war","ukraine",
        "nato","israel","un ","g20","imf","world bank","foreign",
        "diplomat","sanctions","bilateral"
    ]

    for a in general:
        t = (
            (a.get("title","") or "") + " " +
            (a.get("content","") or "")
        ).lower()
        if any(k in t for k in SPORTS):
            cats["sports"].append(a)
        elif any(k in t for k in FINANCE):
            cats["finance"].append(a)
        elif any(k in t for k in INTL):
            cats["international"].append(a)
        else:
            cats["national"].append(a)

    # ── Categorise regional ───────────────────────────────────────
    for a in regional:
        t = (
            (a.get("title","") or "") + " " +
            (a.get("content","") or "") + " " +
            (a.get("url","")    or "")
        ).lower()
        if "rosera" in t:
            cats["rosera"].append(a)
        elif "samastipur" in t:
            cats["samastipur"].append(a)
        else:
            cats["bihar"].append(a)

    return cats


# ── Sarvam — cached per content ───────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def build_summary(articles_json, label):
    articles = json.loads(articles_json)
    if not articles:
        return None
    headlines = "\n".join(
        f"- {(a.get('title','') or '').strip()}: "
        f"{(a.get('content','') or '')[:180].strip()}"
        for a in articles[:7]
    )
    prompt = (
        f"Write a 5-point breaking news brief for {label}. "
        f"Each point covers one story in 2 clear sentences. "
        f"Include names, numbers, facts. "
        f"Start each with •. No headings. Only use info given:\n\n"
        f"{headlines}"
    )
    return sarvam_call(prompt)


@st.cache_data(ttl=1800, show_spinner=False)
def build_words(articles_json):
    articles = json.loads(articles_json)
    if not articles:
        return None
    text = " ".join(
        (a.get("title","") or "") + " " +
        (a.get("content","") or "")[:150]
        for a in articles[:6]
    )[:2000]
    prompt = (
        f"Extract 8 difficult English words from this news text. "
        f"Return ONLY a JSON array, no markdown:\n"
        f'[{{"word":"...","meaning":"...","usage":"..."}}]\n\n'
        f"Text: {text}"
    )
    result = sarvam_call(prompt)
    if not result:
        return None
    clean = re.sub(r"```json|```", "", result).strip()
    try:
        m = re.search(r'\[.*\]', clean, re.DOTALL)
        if m:
            return json.loads(m.group())[:8]
    except:
        pass
    return None


def to_json(articles):
    return json.dumps(
        [{"title":          a.get("title",""),
          "content":        a.get("content",""),
          "url":            a.get("url",""),
          "source":         a.get("source",""),
          "published_date": a.get("published_date","")}
         for a in articles],
        ensure_ascii=False
    )


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
    if not articles:
        st.caption(f"No breaking {label} news right now.")
        return

    aj  = to_json(articles)
    sv  = get_key("SARVAM_API_KEY")

    # ── 1. AI Summary ─────────────────────────────────────────────
    st.markdown("**📰 Breaking News Summary**")
    if sv:
        summary = build_summary(aj, label)
        if summary:
            st.write(summary)
        else:
            for a in articles[:5]:
                t = (a.get("title","") or "").strip()
                if t:
                    st.write(f"• {t}")
    else:
        for a in articles[:5]:
            t = (a.get("title","") or "").strip()
            if t:
                st.write(f"• {t}")

    st.markdown("")

    # ── 2. Word Intelligence ──────────────────────────────────────
    if sv:
        words = build_words(aj)
        if words:
            st.markdown("**📚 Word Intelligence**")
            cols = st.columns(2)
            for i, w in enumerate(words):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{w.get('word','').upper()}**")
                        st.write(f"📖 {w.get('meaning','')}")
                        st.caption(f"✏️ _{w.get('usage','')}_")
            st.markdown("")

    # ── 3. Reference Links ────────────────────────────────────────
    st.markdown("**🔗 Sources**")
    for a in articles[:8]:
        title    = (a.get("title","")   or "Untitled").strip()
        url      = (a.get("url","")     or "").strip()
        source   = (a.get("source","")  or "").strip().upper()
        time_str = format_time(a.get("published_date",""))
        meta     = " · ".join(filter(None, [source, time_str]))
        display  = f"{title[:70]}{'…' if len(title)>70 else ''}"
        if meta:
            display += f"  —  {meta}"
        if url:
            st.markdown(f"- [{display}]({url})")
        else:
            st.markdown(f"- {display}")


# ════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-box">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Breaking news · AI curated · Bihar & India</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 2])
with col1:
    if st.button("🔄 Refresh", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col2:
    st.caption(f"🕐 {now_ist().strftime('%d %b %Y, %I:%M %p')} IST")
with col3:
    st.caption("Auto-refreshes every 30 min · 2 Tavily credits")

st.divider()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# ── Load everything upfront ───────────────────────────────────────
with st.spinner("Fetching breaking news…"):
    news = fetch_all_news()

if not news or all(len(v) == 0 for v in news.values()):
    st.warning("No results. Check Tavily key.")
    st.stop()

# ── Pre-warm Sarvam for all categories ───────────────────────────
sv = get_key("SARVAM_API_KEY")
if sv:
    cats_to_warm = [
        ("national",      "India national"),
        ("international", "world international"),
        ("finance",       "India finance and markets"),
        ("sports",        "India sports and cricket"),
        ("bihar",         "Bihar"),
        ("samastipur",    "Samastipur"),
        ("rosera",        "Rosera"),
    ]
    bar = st.progress(0, text="Generating AI summaries…")
    for i, (cat, label) in enumerate(cats_to_warm):
        arts = news.get(cat, [])
        if arts:
            aj = to_json(arts)
            build_summary(aj, label)
            build_words(aj)
        bar.progress((i + 1) / len(cats_to_warm),
                     text=f"Processing {label}…")
    bar.empty()

# ── Stats ─────────────────────────────────────────────────────────
total = sum(len(v) for v in news.values())
c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, emoji, lbl, cat in [
    (c1, "🏠", "National",      "national"),
    (c2, "🌍", "Internatl",     "international"),
    (c3, "💰", "Finance",       "finance"),
    (c4, "⚽", "Sports",        "sports"),
    (c5, "📍", "Bihar",         "bihar"),
    (c6, "📰", "Total",         None),
]:
    with col:
        with st.container(border=True):
            count = total if cat is None else len(news.get(cat, []))
            st.metric(label=f"{emoji} {lbl}", value=count)

st.divider()

# ── Tabs — all pre-loaded ─────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Bihar & Regional",
])

with tab1:
    st.subheader("🏠 National Breaking News")
    render_section(news.get("national", []), "India national")

with tab2:
    st.subheader("🌍 International Breaking News")
    render_section(news.get("international", []), "world international")

with tab3:
    st.subheader("💰 Finance & Markets")
    render_section(news.get("finance", []), "India finance and markets")

with tab4:
    st.subheader("⚽ Sports")
    render_section(news.get("sports", []), "India sports and cricket")

with tab5:
    st.subheader("📍 Bihar & Regional")

    bihar  = news.get("bihar",      [])
    sams   = news.get("samastipur", [])
    rosera = news.get("rosera",     [])

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
    f"Bharat News AI · "
    f"{now_ist().strftime('%d %b %Y, %I:%M %p')} IST · "
    f"2 credits/refresh · 30 min cache"
)
