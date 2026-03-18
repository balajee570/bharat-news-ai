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


# ── Junk filter ───────────────────────────────────────────────────
JUNK_TITLES = [
    "breaking news today", "latest news today", "top stories",
    "live updates", "news headlines", "today's news",
    "cricket news today", "breaking world news", "live cricket score",
    "expert reviews", "latest and breaking", "india news today",
]
JUNK_DOMAINS = [
    "google.com", "yahoo.com", "msn.com",
    "apple.news", "flipboard.com",
]

def is_junk(article):
    title   = (article.get("title",   "") or "").lower().strip()
    url     = (article.get("url",     "") or "").lower()
    content = (article.get("content", "") or "").strip()
    if len(content) < 80:
        return True
    if any(p in title for p in JUNK_TITLES):
        return True
    if any(d in url for d in JUNK_DOMAINS):
        return True
    return False


# ── Keywords ──────────────────────────────────────────────────────
SPORTS  = [
    "cricket","ipl","wicket","batting","bowling","odi","t20",
    "icc","bcci","football","fifa","tennis","badminton",
    "hockey","olympics","sports","tournament","medal","squad",
    "innings","run rate","world cup","league","player","match score"
]
FINANCE = [
    "nse","bse","sensex","nifty","stock market","share price",
    "rupee","rbi","inflation","interest rate","ipo","sebi",
    "profit","earnings","forex","economy","crude oil",
    "gold price","mutual fund","budget","fiscal","quarterly"
]
INTL    = [
    "usa","united states","china","russia","europe",
    "united kingdom","pakistan","war","ukraine","nato",
    "israel","gaza","united nations","g20","imf",
    "world bank","foreign minister","diplomat","sanctions",
    "bilateral","global","international"
]


# ── 2 Tavily calls — 10 min cache ────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        return {}

    client = TavilyClient(api_key=key)

    now       = now_ist()
    today_str = now.strftime("%d %B %Y")   # 18 March 2026
    hour_str  = now.strftime("%I %p")      # 03 PM
    day_name  = now.strftime("%A")         # Wednesday

    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
        "bihar":         [],
        "samastipur":    [],
        "rosera":        [],
    }

    # ── Call 1 — National + International ────────────────────────
    try:
        r1 = client.search(
            query=(
                f"India breaking news {day_name} {today_str} {hour_str} "
                f"Modi government parliament policy minister "
                f"world international diplomacy foreign latest"
            ),
            search_depth="advanced",
            max_results=15,
            days=1
        )
        results = sorted(
            [a for a in r1.get("results", []) if not is_junk(a)],
            key=lambda x: x.get("published_date", "") or "",
            reverse=True
        )
        for a in results:
            t = (
                (a.get("title",   "") or "") + " " +
                (a.get("content", "") or "")
            ).lower()
            if any(k in t for k in INTL):
                cats["international"].append(a)
            else:
                cats["national"].append(a)
    except:
        pass

    # ── Call 2 — Finance + Sports + Regional ─────────────────────
    try:
        r2 = client.search(
            query=(
                f"India breaking news {day_name} {today_str} {hour_str} "
                f"stock market NSE BSE cricket IPL sports "
                f"Bihar Patna Samastipur Rosera latest"
            ),
            search_depth="advanced",
            max_results=20,
            days=2
        )
        results = sorted(
            [a for a in r2.get("results", []) if not is_junk(a)],
            key=lambda x: x.get("published_date", "") or "",
            reverse=True
        )
        for a in results:
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
            elif any(k in t for k in SPORTS):
                cats["sports"].append(a)
            elif any(k in t for k in FINANCE):
                cats["finance"].append(a)
            else:
                cats["national"].append(a)
    except:
        pass

    return cats


def to_json(articles):
    return json.dumps(
        [{"title":          (a.get("title",          "") or ""),
          "content":        (a.get("content",        "") or ""),
          "url":            (a.get("url",            "") or ""),
          "source":         (a.get("source",         "") or ""),
          "published_date": (a.get("published_date", "") or "")}
         for a in articles],
        ensure_ascii=False
    )


@st.cache_data(ttl=600, show_spinner=False)
def build_summary(articles_json, label):
    articles = json.loads(articles_json)
    if not articles:
        return None
    headlines = "\n".join(
        f"- {(a.get('title','') or '').strip()}: "
        f"{(a.get('content','') or '')[:200].strip()}"
        for a in articles[:8]
    )
    prompt = (
        f"You are a news editor. Write a breaking news brief "
        f"for the {label} section.\n\n"
        f"Rules:\n"
        f"- 5 bullet points\n"
        f"- Each bullet = one specific story, 2 sentences\n"
        f"- Include real names, numbers, locations\n"
        f"- Start each with •\n"
        f"- Use ONLY info from articles below\n"
        f"- No generic statements\n\n"
        f"Articles:\n{headlines}"
    )
    return sarvam_call(prompt)


@st.cache_data(ttl=600, show_spinner=False)
def build_words(articles_json):
    articles = json.loads(articles_json)
    if not articles:
        return None
    text = " ".join(
        (a.get("title","") or "") + " " +
        (a.get("content","") or "")[:200]
        for a in articles[:8]
    )[:2500]
    prompt = (
        f"Extract 8 difficult English words from this news text.\n"
        f"Return ONLY a valid JSON array. No markdown. No extra text.\n"
        f'[{{"word":"...","meaning":"one sentence definition",'
        f'"usage":"example sentence using the word"}}]\n\n'
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
        st.caption(f"No breaking {label} news found right now.")
        return

    aj = to_json(articles)
    sv = get_key("SARVAM_API_KEY")

    # ── 1. Summary ────────────────────────────────────────────────
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

    # ── 3. References ─────────────────────────────────────────────
    st.markdown("**🔗 Sources**")
    for a in articles[:8]:
        title    = (a.get("title","")   or "Untitled").strip()
        url      = (a.get("url","")     or "").strip()
        source   = (a.get("source","")  or "").strip().upper()
        time_str = format_time(a.get("published_date",""))
        meta     = " · ".join(filter(None, [source, time_str]))
        display  = f"{title[:72]}{'…' if len(title)>72 else ''}"
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
    st.caption("Auto-refreshes every 10 min · 2 Tavily credits")

st.divider()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# ── Load upfront ──────────────────────────────────────────────────
with st.spinner("Fetching breaking news…"):
    news = fetch_all_news()

total = sum(len(v) for v in news.values())
if total == 0:
    st.warning("No results. Check Tavily key.")
    st.stop()

# ── Pre-warm Sarvam ───────────────────────────────────────────────
sv = get_key("SARVAM_API_KEY")
if sv:
    warm_cats = [
        ("national",      "India national"),
        ("international", "world international"),
        ("finance",       "India finance"),
        ("sports",        "India sports"),
        ("bihar",         "Bihar"),
        ("samastipur",    "Samastipur"),
        ("rosera",        "Rosera"),
    ]
    bar = st.progress(0, text="Generating AI summaries…")
    for i, (cat, label) in enumerate(warm_cats):
        arts = news.get(cat, [])
        if arts:
            aj = to_json(arts)
            build_summary(aj, label)
            build_words(aj)
        bar.progress(
            (i + 1) / len(warm_cats),
            text=f"Processing {label}…"
        )
    bar.empty()

# ── Stats ─────────────────────────────────────────────────────────
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

# ── Tabs ──────────────────────────────────────────────────────────
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
    f"2 credits/refresh · 10 min cache"
)
