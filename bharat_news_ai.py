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
            timeout=45
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

def is_junk_regional(article):
    """Relaxed filter for local news — shorter content is normal."""
    url     = (article.get("url",     "") or "").lower()
    content = (article.get("content", "") or "").strip()
    if len(content) < 40:
        return True
    if any(d in url for d in JUNK_DOMAINS):
        return True
    return False


# ── Tight non-overlapping keywords ───────────────────────────────
INTL_EXACT = [
    "donald trump", "xi jinping", "vladimir putin", "nato",
    "white house", "pentagon", "united nations", "european union",
    "ukraine war", "gaza strip", "israel hamas", "imf loan",
    "world bank", "g7 summit", "g20 summit", "us sanctions",
    "elon musk", "tariff", "trade war"
]
INTL_WORDS = [
    "usa", "united states", "china", "russia", "europe",
    "united kingdom", "pakistan army", "ukraine", "israel",
    "taliban", "iran nuclear", "north korea", "taiwan strait",
    "foreign minister", "ambassador", "bilateral talks",
    "international sanctions"
]
SPORTS_EXACT = [
    "ipl 2025", "ipl 2026", "test match", "one day international",
    "t20 international", "icc world cup", "bcci", "rohit sharma",
    "virat kohli", "jasprit bumrah", "ms dhoni", "fifa world cup",
    "us open tennis", "wimbledon", "olympic medal",
    "pro kabaddi", "indian super league football"
]
SPORTS_WORDS = [
    "cricket wicket", "batting innings", "bowling figures",
    "run chase", "match score", "over remaining",
    "football goal", "tennis grand slam",
    "badminton championship", "hockey world cup",
    "athletics gold medal", "swimming championship"
]
FINANCE_EXACT = [
    "sensex", "nifty 50", "bse 500", "nse midcap",
    "rbi repo rate", "rbi monetary policy", "sebi circular",
    "ipo listing", "quarterly earnings", "gdp growth rate",
    "rupee dollar", "crude oil price", "gold rate today",
    "mutual fund nav", "inflation data", "cpi data", "wpi data",
    "trade deficit", "forex reserve", "current account deficit"
]
FINANCE_WORDS = [
    "stock market crash", "market rally", "nifty gains",
    "sensex falls", "share price", "profit booking",
    "interest rate hike", "bond yield", "fiscal deficit",
    "budget allocation", "tax revenue", "export import"
]


def classify(article):
    t = (
        (article.get("title",   "") or "") + " " +
        (article.get("content", "") or "")
    ).lower()
    url   = (article.get("url", "") or "").lower()
    t_url = t + " " + url

    if "rosera"     in t_url: return "rosera"
    if "samastipur" in t_url: return "samastipur"
    if "bihar"      in t_url or "patna" in t_url: return "bihar"
    if any(k in t for k in SPORTS_EXACT):  return "sports"
    if any(k in t for k in SPORTS_WORDS):  return "sports"
    if any(k in t for k in FINANCE_EXACT): return "finance"
    if any(k in t for k in FINANCE_WORDS): return "finance"
    if any(k in t for k in INTL_EXACT):    return "international"
    if any(k in t for k in INTL_WORDS):    return "international"
    return "national"


def tavily_search(client, query, max_results, days):
    try:
        r = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            days=days,
            topic="news"
        )
        return r.get("results", [])
    except:
        try:
            r = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                days=days
            )
            return r.get("results", [])
        except:
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

    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
        "bihar":         [],
        "samastipur":    [],
        "rosera":        [],
    }

    q1 = (
        f"India breaking news {day_name} {today_str} "
        f"government parliament Modi minister policy "
        f"world international diplomacy geopolitics"
    )
    q2 = (
        f"India breaking news {day_name} {today_str} "
        f"NSE BSE Sensex Nifty stock market RBI economy "
        f"cricket IPL match score"
    )
    q3 = f"Bihar Patna Samastipur Rosera news {today_str}"

    # All 3 calls in parallel
    with ThreadPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(tavily_search, client, q1, 15, 1)
        f2 = ex.submit(tavily_search, client, q2, 15, 1)
        f3 = ex.submit(tavily_search, client, q3, 10, 5)
        r1 = f1.result()
        r2 = f2.result()
        r3 = f3.result()

    # Call 1 → national + international
    for a in sorted(
        [x for x in r1 if not is_junk(x)],
        key=lambda x: x.get("published_date", "") or "",
        reverse=True
    ):
        cat = classify(a)
        cats[cat if cat in ("national","international") else "national"].append(a)

    # Call 2 → finance + sports
    for a in sorted(
        [x for x in r2 if not is_junk(x)],
        key=lambda x: x.get("published_date", "") or "",
        reverse=True
    ):
        cat = classify(a)
        cats[cat if cat in ("finance","sports") else "finance"].append(a)

    # Call 3 → regional only, relaxed filter
    for a in sorted(
        [x for x in r3 if not is_junk_regional(x)],
        key=lambda x: x.get("published_date", "") or "",
        reverse=True
    ):
        t_url = (
            (a.get("title",   "") or "") + " " +
            (a.get("content", "") or "") + " " +
            (a.get("url",     "") or "")
        ).lower()
        if "rosera"     in t_url: cats["rosera"].append(a)
        elif "samastipur" in t_url: cats["samastipur"].append(a)
        else: cats["bihar"].append(a)

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
        f"for the {label} section.\n"
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
def build_words(articles_json, label):
    """
    Word intelligence — separate prompt per section.
    Returns list of dicts or empty list (never None).
    """
    articles = json.loads(articles_json)
    if not articles:
        return []

    # Build combined text from titles + content
    text = " ".join(
        (a.get("title","") or "") + " " +
        (a.get("content","") or "")[:200]
        for a in articles[:8]
    )[:2500]

    if not text.strip():
        return []

    prompt = (
        f"From this {label} news text, extract 8 difficult or "
        f"important English words.\n"
        f"Return ONLY a JSON array. No markdown. No explanation. "
        f"No text before or after the array.\n"
        f"Format exactly:\n"
        f'[{{"word":"example","meaning":"clear one sentence meaning",'
        f'"usage":"a sentence using this word in context"}}]\n\n'
        f"Text:\n{text}"
    )

    result = sarvam_call(prompt)

    # No response
    if not result:
        return []

    # Strip markdown fences if present
    clean = re.sub(r"```json|```", "", result).strip()

    # Try direct parse
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, list) and parsed:
            return parsed[:8]
    except:
        pass

    # Try extracting array from within response
    try:
        m = re.search(r'\[.*?\]', clean, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            if isinstance(parsed, list) and parsed:
                return parsed[:8]
    except:
        pass

    return []


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


def render_section(articles, label, summary, words):
    if not articles:
        st.caption(f"No breaking {label} news found right now.")
        return

    # ── 1. Summary ────────────────────────────────────────────────
    st.markdown("**📰 Breaking News Summary**")
    if summary:
        st.write(summary)
    else:
        for a in articles[:5]:
            t = (a.get("title","") or "").strip()
            if t:
                st.write(f"• {t}")

    st.markdown("")

    # ── 2. Word Intelligence ──────────────────────────────────────
    st.markdown("**📚 Word Intelligence**")
    if words and len(words) > 0:
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
                    if meaning:
                        st.write(f"📖 {meaning}")
                    if usage:
                        st.caption(f"✏️ _{usage}_")
    else:
        st.caption("Word intelligence unavailable for this section.")

    st.markdown("")

    # ── 3. References ─────────────────────────────────────────────
    st.markdown("**🔗 Sources**")
    shown = 0
    for a in articles[:8]:
        title    = (a.get("title","")   or "").strip()
        url      = (a.get("url","")     or "").strip()
        source   = (a.get("source","")  or "").strip().upper()
        time_str = format_time(a.get("published_date",""))

        if not title or not url:
            continue

        meta    = " · ".join(filter(None, [source, time_str]))
        display = f"{title[:72]}{'…' if len(title)>72 else ''}"
        if meta:
            display += f"  —  {meta}"

        st.markdown(f"- [{display}]({url})")
        shown += 1

    if shown == 0:
        st.caption("No source links available.")


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
    st.caption("Auto-refreshes every 10 min · 3 Tavily credits")

st.divider()

if not get_key("TAVILY_API_KEY"):
    st.error("TAVILY_API_KEY missing from secrets.toml")
    st.stop()

# Step 1 — Parallel Tavily fetch (3 calls simultaneously)
with st.spinner("📡 Fetching breaking news…"):
    news = fetch_all_news()

total = sum(len(v) for v in news.values())
if total == 0:
    st.warning("No results. Check Tavily key.")
    st.stop()

# Step 2 — Parallel Sarvam (summary + words simultaneously)
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

    bar = st.progress(0, text="Preparing news intelligence…")

    def process_cat(cat_label):
        cat, label = cat_label
        aj      = to_json(news[cat])
        summary = build_summary(aj, label)
        words   = build_words(aj, label)
        return cat, summary, words

    with ThreadPoolExecutor(max_workers=len(active)) as ex:
        futures = {ex.submit(process_cat, cl): cl for cl in active}
        done    = 0
        for future in as_completed(futures):
            try:
                cat, s, w      = future.result()
                summaries[cat] = s
                words_map[cat] = w if w else []
            except:
                pass
            done += 1
            bar.progress(
                done / len(active),
                text=f"Processed {done}/{len(active)} sections…"
            )

    bar.progress(1.0, text="Done!")
    bar.empty()

# Step 3 — Stats
c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, emoji, lbl, cat in [
    (c1, "🏠", "National",  "national"),
    (c2, "🌍", "Internatl", "international"),
    (c3, "💰", "Finance",   "finance"),
    (c4, "⚽", "Sports",    "sports"),
    (c5, "📍", "Bihar",     "bihar"),
    (c6, "📰", "Total",     None),
]:
    with col:
        with st.container(border=True):
            count = total if cat is None else len(news.get(cat, []))
            st.metric(label=f"{emoji} {lbl}", value=count)

st.divider()

# Step 4 — Tabs (all instant)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Bihar & Regional",
])

with tab1:
    st.subheader("🏠 National Breaking News")
    render_section(
        news.get("national", []), "India national",
        summaries.get("national"), words_map.get("national", [])
    )

with tab2:
    st.subheader("🌍 International Breaking News")
    render_section(
        news.get("international", []), "world international",
        summaries.get("international"), words_map.get("international", [])
    )

with tab3:
    st.subheader("💰 Finance & Markets")
    render_section(
        news.get("finance", []), "India finance and markets",
        summaries.get("finance"), words_map.get("finance", [])
    )

with tab4:
    st.subheader("⚽ Sports")
    render_section(
        news.get("sports", []), "India sports and cricket",
        summaries.get("sports"), words_map.get("sports", [])
    )

with tab5:
    st.subheader("📍 Bihar & Regional")
    bihar  = news.get("bihar",      [])
    sams   = news.get("samastipur", [])
    rosera = news.get("rosera",     [])

    if bihar:
        st.markdown("### Bihar")
        render_section(
            bihar, "Bihar",
            summaries.get("bihar"), words_map.get("bihar", [])
        )
        st.divider()
    if sams:
        st.markdown("### Samastipur")
        render_section(
            sams, "Samastipur",
            summaries.get("samastipur"), words_map.get("samastipur", [])
        )
        st.divider()
    if rosera:
        st.markdown("### Rosera")
        render_section(
            rosera, "Rosera",
            summaries.get("rosera"), words_map.get("rosera", [])
        )
    if not any([bihar, sams, rosera]):
        st.info("No regional results today.")

st.divider()
st.caption(
    f"Bharat News AI · "
    f"{now_ist().strftime('%d %b %Y, %I:%M %p')} IST · "
    f"3 credits · 10 min cache"
)
