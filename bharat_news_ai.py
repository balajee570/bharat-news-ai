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


# ── Session state init ────────────────────────────────────────────
for k, v in [
    ("general_raw",  None),
    ("regional_raw", None),
    ("fetched_at",   None),
]:
    if k not in st.session_state:
        st.session_state[k] = v


def get_key(k):
    try:
        return st.secrets[k]
    except:
        return ""


# ── Sarvam call ───────────────────────────────────────────────────
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


# ── Recency filter with safe fallbacks ───────────────────────────
def filter_recent(articles, hours):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = []
    for a in articles:
        pub = a.get("published_date", "")
        if not pub:
            result.append(a)
            continue
        try:
            d = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d >= cutoff:
                result.append(a)
        except:
            result.append(a)
    return result


def smart_filter(articles, windows=(2, 6, 24, 72), min_count=3):
    for h in windows:
        result = filter_recent(articles, h)
        if len(result) >= min_count:
            return result, h
    return articles, 999  # Safety net — return all


# ── Tavily fetch — 2 calls ────────────────────────────────────────
def fetch_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        st.error("TAVILY_API_KEY missing from secrets.toml")
        return [], []

    client = TavilyClient(api_key=key)
    general, regional = [], []

    with st.spinner("Fetching general news…"):
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

    with st.spinner("Fetching Bihar & regional news…"):
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

    return general, regional


# ── Categorise general ────────────────────────────────────────────
def categorise_general(articles):
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
        "medal", "coach", "squad", "innings", "run chase",
        "player of the match"
    ]
    FINANCE = [
        "nse", "bse", "sensex", "nifty", "stock", "share price",
        "mutual fund", "market cap", "rupee", "gdp",
        "finance", "budget", "inflation", "rbi", "interest rate",
        "investment", "ipo", "sebi", "fiscal", "revenue", "profit",
        "quarterly results", "earnings", "forex"
    ]
    INTL = [
        "world", "global", "usa", "united states", "china", "russia",
        "europe", "uk ", "united kingdom", "pakistan", "international",
        "war", "ukraine", "nato", "israel", "gaza", "un ", "g20",
        "imf", "world bank", "foreign", "diplomat", "sanctions"
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
    cats = {
        "rosera":     [],
        "samastipur": [],
        "bihar":      [],
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
        else:
            cats["bihar"].append(a)

    return {k: v for k, v in cats.items() if v}


# ── Sarvam: structured news brief per category ────────────────────
def get_ai_brief(articles, category_name, brief_key):
    """
    Generates a structured news brief using Sarvam.
    Result cached in session state so button click doesn't re-call.
    """
    cache_key = f"brief_{brief_key}"

    if cache_key in st.session_state:
        st.markdown(st.session_state[cache_key])
        return

    if not get_key("SARVAM_API_KEY"):
        st.caption("Add SARVAM_API_KEY for AI briefs.")
        return

    if not articles:
        return

    if st.button(f"✦ Generate AI News Brief", key=f"btn_{brief_key}"):
        combined = "\n\n".join(
            f"Headline: {(a.get('title','') or '').strip()}\n"
            f"Details: {(a.get('content','') or '')[:300].strip()}"
            for a in articles[:8]
        )

        prompt = (
            f"You are a news editor. Based on these {category_name} news items, "
            f"write a clean, structured news brief.\n\n"
            f"Format:\n"
            f"- 3 to 5 key points as bullet items\n"
            f"- Each bullet: one clear sentence summarising one story\n"
            f"- Be factual and specific\n"
            f"- Do not add any headings or labels\n\n"
            f"News items:\n{combined}"
        )

        with st.spinner("Generating brief…"):
            result = sarvam(prompt)

        if result:
            st.session_state[cache_key] = result
            st.markdown(result)
        else:
            st.warning("Could not generate brief. Try again.")


# ── Reference links ───────────────────────────────────────────────
def render_links(articles, max_n=6):
    if not articles:
        return
    st.markdown("**📎 Reference Links**")
    for a in articles[:max_n]:
        title = (a.get("title", "") or "Untitled").strip()
        url   = (a.get("url",   "") or "").strip()
        pub   = (a.get("published_date", "") or "")

        time_str = ""
        if pub:
            try:
                d     = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                d_ist = d.astimezone(IST)
                if d_ist.date() == now_ist().date():
                    time_str = d_ist.strftime("%I:%M %p")
                else:
                    time_str = d_ist.strftime("%d %b")
            except:
                time_str = ""

        label = f"{title[:70]}{'…' if len(title)>70 else ''}"
        if time_str:
            label += f"  ·  {time_str} IST"

        if url:
            st.markdown(f"- [{label}]({url})")
        else:
            st.markdown(f"- {label}")


# ── Word Intelligence ─────────────────────────────────────────────
def word_intelligence(articles, section_key):
    """
    Uses session state — button click won't lose data.
    Cache result so no re-call on rerun.
    """
    cache_key = f"wi_{section_key}"

    if cache_key in st.session_state:
        st.markdown("**📚 Difficult Words from This Section**")
        for i, w in enumerate(st.session_state[cache_key], 1):
            with st.container(border=True):
                st.markdown(f"**#{i} {w.get('word','').upper()}**")
                st.write(f"📖 **Meaning:** {w.get('meaning','')}")
                st.write(f"✏️ **Usage:** _{w.get('usage','')}_")
                st.caption(f"💡 {w.get('description','')}")
        return

    if not get_key("SARVAM_API_KEY"):
        st.caption("Add SARVAM_API_KEY for Word Intelligence.")
        return

    if not articles:
        return

    if st.button(
        "📚 Word Intelligence",
        key=f"wibtn_{section_key}"
    ):
        combined = " ".join(
            f"{(a.get('title','') or '')} "
            f"{(a.get('content','') or '')[:200]}"
            for a in articles[:10]
        )[:3000]

        with st.spinner("Extracting words…"):
            result = sarvam(
                f"Extract exactly 10 difficult English words from this text. "
                f"Return ONLY a valid JSON array, no markdown:\n"
                f'[{{"word":"...","meaning":"...","usage":"...","description":"..."}}]\n\n'
                f"Text: {combined}"
            )

        if not result:
            st.warning("No response. Try again.")
            return

        result = re.sub(r"```json|```", "", result).strip()
        try:
            m = re.search(r'\[.*\]', result, re.DOTALL)
            if m:
                words = json.loads(m.group())[:10]
                st.session_state[cache_key] = words
                st.markdown("**📚 Difficult Words from This Section**")
                for i, w in enumerate(words, 1):
                    with st.container(border=True):
                        st.markdown(f"**#{i} {w.get('word','').upper()}**")
                        st.write(f"📖 **Meaning:** {w.get('meaning','')}")
                        st.write(f"✏️ **Usage:** _{w.get('usage','')}_")
                        st.caption(f"💡 {w.get('description','')}")
            else:
                st.warning("Could not parse. Try again.")
        except json.JSONDecodeError:
            st.warning("Parse failed. Try again.")


# ── Render one category section ───────────────────────────────────
def render_section(articles, label, brief_key):
    if not articles:
        st.caption(f"No {label} news found right now.")
        return

    st.caption(f"{len(articles)} articles found")

    # AI Brief — structured Sarvam summary
    get_ai_brief(articles, label, brief_key)

    st.divider()

    # Reference links at bottom
    render_links(articles)

    st.divider()

    # Word Intelligence
    word_intelligence(articles, brief_key)


# ════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-box">
    <h1>🇮🇳 Bharat News AI</h1>
    <p>Real-time news · AI curated briefs · Bihar & India</p>
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
    if st.session_state.fetched_at:
        st.caption(
            f"🕐 Last fetched: {st.session_state.fetched_at}"
            f"  ·  2 search credits per refresh"
        )
    else:
        st.caption(
            f"🕐 {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
            f"  ·  2 search credits per refresh"
        )

st.divider()

# ── Fetch on button click — store in session state ────────────────
if fetch_btn:
    if not get_key("TAVILY_API_KEY"):
        st.error("TAVILY_API_KEY missing from secrets.toml")
        st.stop()

    general_raw, regional_raw = fetch_news()

    if not general_raw and not regional_raw:
        st.warning("No results. Check your API keys.")
        st.stop()

    # Smart filter
    general_raw,  _ = smart_filter(general_raw,  windows=(2, 6, 24),    min_count=4)
    regional_raw, _ = smart_filter(regional_raw, windows=(6, 24, 72),   min_count=2)

    # Store in session state
    st.session_state.general_raw  = general_raw
    st.session_state.regional_raw = regional_raw
    st.session_state.fetched_at   = now_ist().strftime("%d %b %Y, %I:%M %p IST")

    # Clear cached AI briefs and word intelligence on refresh
    for k in list(st.session_state.keys()):
        if k.startswith("brief_") or k.startswith("wi_"):
            del st.session_state[k]

# ── Gate: if no data yet, show welcome ───────────────────────────
if st.session_state.general_raw is None:
    st.info(
        "Click **Refresh News** to load today's headlines.\n\n"
        "**Sections:** National · International · Finance · "
        "Sports · Bihar · Samastipur · Rosera\n\n"
        "Each section shows:\n"
        "- **AI News Brief** — curated summary (click to generate)\n"
        "- **Reference Links** — source articles\n"
        "- **Word Intelligence** — 10 difficult words explained\n\n"
        "**Credits:** 2 Tavily credits per refresh."
    )
    st.stop()

# ── Use session state data ────────────────────────────────────────
general_raw  = st.session_state.general_raw
regional_raw = st.session_state.regional_raw

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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Bihar & Regional",
])

with tab1:
    st.subheader("🏠 National News")
    render_section(
        gen_cats.get("national", []),
        "India national", "national"
    )

with tab2:
    st.subheader("🌍 International News")
    render_section(
        gen_cats.get("international", []),
        "world international", "intl"
    )

with tab3:
    st.subheader("💰 Finance & Markets")
    render_section(
        gen_cats.get("finance", []),
        "India finance and markets", "finance"
    )

with tab4:
    st.subheader("⚽ Sports")
    render_section(
        gen_cats.get("sports", []),
        "India sports and cricket", "sports"
    )

with tab5:
    st.subheader("📍 Bihar & Regional News")

    bihar  = reg_cats.get("bihar",      [])
    sams   = reg_cats.get("samastipur", [])
    rosera = reg_cats.get("rosera",     [])

    if bihar:
        st.markdown("### Bihar")
        render_section(bihar, "Bihar", "bihar")
        st.divider()

    if sams:
        st.markdown("### Samastipur")
        render_section(sams, "Samastipur", "samastipur")
        st.divider()

    if rosera:
        st.markdown("### Rosera")
        render_section(rosera, "Rosera", "rosera")

    if not any([bihar, sams, rosera]):
        st.info(
            "No hyper-local results today. "
            "Bihar news may appear in the National tab."
        )

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · 2 credits/refresh"
)
