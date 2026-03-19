import streamlit as st
import requests
import json
import re
from datetime import datetime, timezone, timedelta
from tavily import TavilyClient
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    """Single Sarvam call with retry on None."""
    key = get_key("SARVAM_API_KEY")
    if not key:
        return None
    for _ in range(2):  # retry once
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
                timeout=45
            )
            if resp.status_code != 200:
                continue
            choices = resp.json().get("choices", [])
            if not choices:
                continue
            content = choices[0].get("message", {}).get("content")
            if content:
                return content.strip()
        except:
            continue
    return None


JUNK_DOMAINS = ["google.com", "yahoo.com", "msn.com", "apple.news", "flipboard.com"]
JUNK_TITLES  = [
    "breaking news today", "latest news today", "top stories",
    "live updates", "news headlines", "today's news",
    "cricket news today", "breaking world news", "live cricket score",
    "latest and breaking", "india news today",
]

def is_junk(a):
    title   = (a.get("title",   "") or "").lower()
    url     = (a.get("url",     "") or "").lower()
    content = (a.get("content", "") or "").strip()
    if len(content) < 80: return True
    if any(p in title for p in JUNK_TITLES): return True
    if any(d in url   for d in JUNK_DOMAINS): return True
    return False

def is_junk_regional(a):
    url     = (a.get("url",     "") or "").lower()
    content = (a.get("content", "") or "").strip()
    if len(content) < 30: return True
    if any(d in url for d in JUNK_DOMAINS): return True
    return False


# ── Intl keywords — exact phrases only ───────────────────────────
INTL_KW = [
    "donald trump", "xi jinping", "vladimir putin", "nato",
    "white house", "pentagon", "united nations", "european union",
    "ukraine war", "gaza strip", "israel hamas", "world bank",
    "g7 summit", "g20 summit", "us sanctions", "trade war",
    "pakistan army", "iran nuclear", "north korea", "taiwan strait",
    "foreign minister", "ambassador", "elon musk"
]
SPORTS_KW = [
    "ipl 2025", "ipl 2026", "test match", "one day international",
    "t20 international", "icc world cup", "bcci", "rohit sharma",
    "virat kohli", "jasprit bumrah", "ms dhoni", "fifa world cup",
    "wimbledon", "olympic medal", "pro kabaddi",
    "cricket wicket", "batting innings", "bowling figures",
    "run chase", "match score", "football goal", "tennis grand slam"
]


def split_national_intl(articles):
    """Split Call 1 results into national vs international."""
    national, intl = [], []
    for a in articles:
        if not is_junk(a):
            t = ((a.get("title","") or "") + " " + (a.get("content","") or "")).lower()
            if any(k in t for k in INTL_KW):
                intl.append(a)
            else:
                national.append(a)
    return national, intl


def split_finance_sports(articles):
    """Split Call 2 results into finance vs sports."""
    finance, sports = [], []
    for a in articles:
        if not is_junk(a):
            t = ((a.get("title","") or "") + " " + (a.get("content","") or "")).lower()
            if any(k in t for k in SPORTS_KW):
                sports.append(a)
            else:
                finance.append(a)
    return finance, sports


def split_regional(articles):
    """Split Call 3 results into bihar/samastipur/rosera. NO other classification."""
    bihar, sams, rosera = [], [], []
    for a in articles:
        if not is_junk_regional(a):
            t = (
                (a.get("title",   "") or "") + " " +
                (a.get("content", "") or "") + " " +
                (a.get("url",     "") or "")
            ).lower()
            if "rosera"     in t: rosera.append(a)
            elif "samastipur" in t: sams.append(a)
            else: bihar.append(a)
    return bihar, sams, rosera


def tavily_search(client, query, n, days):
    for attempt in range(2):
        try:
            kwargs = dict(
                query=query,
                search_depth="basic",
                max_results=n,
                days=days
            )
            if attempt == 0:
                kwargs["topic"] = "news"
            r = client.search(**kwargs)
            results = r.get("results", [])
            if results:
                return sorted(
                    results,
                    key=lambda x: x.get("published_date","") or "",
                    reverse=True
                )
        except:
            continue
    return []


@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        return {}

    client    = TavilyClient(api_key=key)
    now       = now_ist()
    today_str = now.strftime("%d %B %Y")
    day_name  = now.strftime("%A")

    # 3 completely isolated queries — zero overlap
    q1 = (
        f"India breaking news {day_name} {today_str} "
        f"government parliament Modi minister policy "
        f"world international diplomacy"
    )
    q2 = (
        f"India breaking news {day_name} {today_str} "
        f"NSE BSE Sensex Nifty RBI economy "
        f"cricket IPL match"
    )
    q3 = f"Bihar Patna Samastipur Rosera latest news {today_str}"

    # Parallel fetch
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(tavily_search, client, q1, 15, 1)
        f2 = ex.submit(tavily_search, client, q2, 15, 1)
        f3 = ex.submit(tavily_search, client, q3, 12, 5)
        r1, r2, r3 = f1.result(), f2.result(), f3.result()

    national, intl        = split_national_intl(r1)
    finance, sports       = split_finance_sports(r2)
    bihar, sams, rosera   = split_regional(r3)

    return {
        "national":      national,
        "international": intl,
        "finance":       finance,
        "sports":        sports,
        "bihar":         bihar,
        "samastipur":    sams,
        "rosera":        rosera,
    }


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
def build_summary(aj, label):
    articles = json.loads(aj)
    if not articles:
        return None
    lines = "\n".join(
        f"- {(a.get('title','') or '').strip()}: "
        f"{(a.get('content','') or '')[:200].strip()}"
        for a in articles[:8]
    )
    return sarvam_call(
        f"Write a 5-point breaking news brief for {label}.\n"
        f"Each point starts with • and covers one story in 2 sentences.\n"
        f"Include names, numbers, facts. Use ONLY info below.\n\n"
        f"{lines}"
    )


@st.cache_data(ttl=600, show_spinner=False)
def build_words(aj, label):
    articles = json.loads(aj)
    if not articles:
        return []

    text = " ".join(
        (a.get("title","") or "") + " " +
        (a.get("content","") or "")[:200]
        for a in articles[:8]
    )[:2500]

    if len(text.strip()) < 50:
        return []

    result = sarvam_call(
        f"From this {label} news text extract 8 difficult English words.\n"
        f"Return ONLY valid JSON array. No markdown. No text before or after.\n"
        f'[{{"word":"w","meaning":"m","usage":"u"}}]\n\n'
        f"Text: {text}"
    )

    if not result:
        return []

    # Clean and parse
    clean = re.sub(r"```json|```", "", result).strip()

    # Try direct
    try:
        p = json.loads(clean)
        if isinstance(p, list) and p:
            return [w for w in p if w.get("word")][:8]
    except:
        pass

    # Try greedy extract
    try:
        m = re.search(r'\[.+\]', clean, re.DOTALL)
        if m:
            p = json.loads(m.group())
            if isinstance(p, list) and p:
                return [w for w in p if w.get("word")][:8]
    except:
        pass

    return []


def fmt_time(pub):
    if not pub:
        return ""
    try:
        d = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(IST)
        return d.strftime("%I:%M %p IST") if d.date() == now_ist().date() else d.strftime("%d %b %Y")
    except:
        return ""


def render_section(articles, label, summary, words):
    # ── Summary ───────────────────────────────────────────────────
    st.markdown("**📰 Breaking News Summary**")
    if summary:
        st.write(summary)
    elif articles:
        for a in articles[:5]:
            t = (a.get("title","") or "").strip()
            if t: st.write(f"• {t}")
    else:
        st.caption(f"No {label} news right now.")
        return

    st.markdown("")

    # ── Word Intelligence ─────────────────────────────────────────
    st.markdown("**📚 Word Intelligence**")
    if words:
        cols = st.columns(2)
        for i, w in enumerate(words):
            word    = (w.get("word",    "") or "").strip()
            meaning = (w.get("meaning", "") or "").strip()
            usage   = (w.get("usage",   "") or "").strip()
            if not word:
                continue
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{word.upper()}**")
                    if meaning: st.write(f"📖 {meaning}")
                    if usage:   st.caption(f"✏️ _{usage}_")
    else:
        st.caption("Not available for this section.")

    st.markdown("")

    # ── Sources ───────────────────────────────────────────────────
    st.markdown("**🔗 Sources**")
    shown = 0
    for a in articles[:8]:
        title = (a.get("title","") or "").strip()
        url   = (a.get("url","")   or "").strip()
        if not title or not url:
            continue
        src  = (a.get("source","") or "").strip().upper()
        ts   = fmt_time(a.get("published_date",""))
        meta = " · ".join(filter(None, [src, ts]))
        txt  = f"{title[:72]}{'…' if len(title)>72 else ''}"
        if meta: txt += f"  —  {meta}"
        st.markdown(f"- [{txt}]({url})")
        shown += 1
    if not shown:
        st.caption("No sources available.")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-box">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Breaking news · AI curated · Bihar & India</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 2])
with c1:
    if st.button("🔄 Refresh", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with c2:
    st.caption(f"🕐 {now_ist().strftime('%d %b %Y, %I:%M %p')} IST")
with c3:
    st.caption("Auto-refreshes every 10 min · 3 Tavily credits")

st.divider()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# ── Fetch ─────────────────────────────────────────────────────────
with st.spinner("📡 Fetching breaking news…"):
    news = fetch_all_news()

total = sum(len(v) for v in news.values())
if total == 0:
    st.warning("No results. Check Tavily key.")
    st.stop()

# ── Pre-compute all AI in parallel ────────────────────────────────
sv = get_key("SARVAM_API_KEY")

CATS_META = [
    ("national",      "India national"),
    ("international", "world international"),
    ("finance",       "India finance and markets"),
    ("sports",        "India sports and cricket"),
    ("bihar",         "Bihar"),
    ("samastipur",    "Samastipur"),
    ("rosera",        "Rosera"),
]

summaries = {}
words_map = {}

if sv:
    active = [(c, l) for c, l in CATS_META if news.get(c)]
    bar    = st.progress(0, text="Preparing AI intelligence…")

    def process(cl):
        cat, label = cl
        aj = to_json(news[cat])
        return cat, build_summary(aj, label), build_words(aj, label)

    with ThreadPoolExecutor(max_workers=len(active)) as ex:
        futs = {ex.submit(process, cl): cl for cl in active}
        done = 0
        for fut in as_completed(futs):
            try:
                cat, s, w      = fut.result()
                summaries[cat] = s
                words_map[cat] = w if isinstance(w, list) else []
            except:
                pass
            done += 1
            bar.progress(done / len(active), text=f"{done}/{len(active)} done…")

    bar.progress(1.0, text="Ready!")
    bar.empty()

# ── Stats ─────────────────────────────────────────────────────────
s1,s2,s3,s4,s5,s6 = st.columns(6)
for col, emoji, lbl, cat in [
    (s1,"🏠","National",     "national"),
    (s2,"🌍","Internatl",    "international"),
    (s3,"💰","Finance",      "finance"),
    (s4,"⚽","Sports",       "sports"),
    (s5,"📍","Bihar",        "bihar"),
    (s6,"📰","Total",        None),
]:
    with col:
        with st.container(border=True):
            st.metric(
                label=f"{emoji} {lbl}",
                value=total if cat is None else len(news.get(cat,[]))
            )

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "🏠 National","🌍 International",
    "💰 Finance","⚽ Sports","📍 Bihar & Regional"
])

with tab1:
    st.subheader("🏠 National Breaking News")
    render_section(news.get("national",[]),"India national",
                   summaries.get("national"),words_map.get("national",[]))

with tab2:
    st.subheader("🌍 International Breaking News")
    render_section(news.get("international",[]),"world international",
                   summaries.get("international"),words_map.get("international",[]))

with tab3:
    st.subheader("💰 Finance & Markets")
    render_section(news.get("finance",[]),"India finance and markets",
                   summaries.get("finance"),words_map.get("finance",[]))

with tab4:
    st.subheader("⚽ Sports")
    render_section(news.get("sports",[]),"India sports and cricket",
                   summaries.get("sports"),words_map.get("sports",[]))

with tab5:
    st.subheader("📍 Bihar & Regional")

    st.markdown("### 🏙️ Bihar")
    if news.get("bihar"):
        render_section(news["bihar"],"Bihar",
                       summaries.get("bihar"),words_map.get("bihar",[]))
    else:
        st.caption("No Bihar news right now.")

    st.divider()

    st.markdown("### 🌆 Samastipur")
    if news.get("samastipur"):
        render_section(news["samastipur"],"Samastipur",
                       summaries.get("samastipur"),words_map.get("samastipur",[]))
    else:
        st.caption("No Samastipur news right now.")

    st.divider()

    st.markdown("### 🏘️ Rosera")
    if news.get("rosera"):
        render_section(news["rosera"],"Rosera",
                       summaries.get("rosera"),words_map.get("rosera",[]))
    else:
        st.caption("No Rosera news right now.")

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · 3 credits · 10 min cache"
)
