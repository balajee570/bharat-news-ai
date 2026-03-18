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


# ── Smart recency filter ──────────────────────────────────────────
def filter_recent(articles, hours):
    """
    Keep articles published within last N hours.
    If article has no date → always include (safer than hiding).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for a in articles:
        pub = a.get("published_date", "")
        if not pub:
            # No date info — include to avoid hiding valid news
            recent.append(a)
            continue
        try:
            d = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d >= cutoff:
                recent.append(a)
        except:
            # Cannot parse date — include to be safe
            recent.append(a)
    return recent


def apply_smart_filter(articles, label,
                        preferred_hours=2,
                        fallback_hours=6,
                        final_fallback_hours=24,
                        min_count=3):
    """
    Try preferred window first.
    If too few → widen to fallback.
    If still too few → widen to final fallback.
    Always returns at least whatever is available.
    """
    result = filter_recent(articles, preferred_hours)
    window = preferred_hours

    if len(result) < min_count:
        result = filter_recent(articles, fallback_hours)
        window = fallback_hours

    if len(result) < min_count:
        result = filter_recent(articles, final_fallback_hours)
        window = final_fallback_hours

    # Absolute safety net — if still empty, return all
    if not result:
        result  = articles
        window  = 999

    return result, window


# ── 2 Tavily calls ────────────────────────────────────────────────
def fetch_news():
    key = get_key("TAVILY_API_KEY")
    if not key:
        st.error("TAVILY_API_KEY missing from secrets.toml")
        return [], []

    client = TavilyClient(api_key=key)

    with st.spinner("Fetching national, international, finance, sports…"):
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


# ── Categorise general ────────────────────────────────────────────
def categorise_general(articles):
    cats = {
        "national":      [],
        "international": [],
        "finance":       [],
        "sports":        [],
    }

    SPORTS_KEYS = [
        "cricket", "ipl", "wicket", "batting", "bowling", "test match",
        "odi", "t20", "icc", "bcci", "football", "fifa", "premier league",
        "tennis", "badminton", "hockey", "kabaddi", "chess", "athletics",
        "olympics", "commonwealth games", "sports", "stadium",
        "tournament", "trophy", "medal", "coach", "squad", "fixture",
        "player of the match", "innings", "over ", "run chase"
    ]
    FINANCE_KEYS = [
        "nse", "bse", "sensex", "nifty", "stock", "share price",
        "mutual fund", "market cap", "rupee", "gdp", "trade deficit",
        "finance", "budget", "inflation", "rbi", "interest rate",
        "investment", "ipo", "sebi", "fiscal", "revenue", "profit",
        "quarterly results", "earnings", "forex", "bond yield"
    ]
    INTL_KEYS = [
        "world", "global", "usa", "united states", "china", "russia",
        "europe", "uk ", "united kingdom", "pakistan", "international",
        "war", "ukraine", "nato", "israel", "gaza", "un ", "g20",
        "imf", "world bank", "foreign", "diplomat", "sanctions",
        "bilateral", "geopolitical"
    ]

    for a in articles:
        t = (
            (a.get("title",   "") or "") + " " +
            (a.get("content", "") or "")
        ).lower()

        if any(k in t for k in SPORTS_KEYS):
            cats["sports"].append(a)
        elif any(k in t for k in FINANCE_KEYS):
            cats["finance"].append(a)
        elif any(k in t for k in INTL_KEYS):
            cats["international"].append(a)
        else:
            cats["national"].append(a)

    return cats


# ── Categorise regional ───────────────────────────────────────────
def categorise_regional(articles):
    cats = {
        "rosera":         [],
        "samastipur":     [],
        "bihar":          [],
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


# ── Render articles ───────────────────────────────────────────────
def render_articles(articles, max_n=6):
    if not articles:
        st.caption("No articles available.")
        return

    for a in articles[:max_n]:
        title   = (a.get("title",   "") or "").strip()
        content = (a.get("content", "") or "")[:250].strip()
        url     = (a.get("url",     "") or "").strip()
        source  = (a.get("source",  "") or "").strip()
        pub     = (a.get("published_date", "") or "")

        time_str = ""
        if pub:
            try:
                d     = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                d_ist = d.astimezone(IST)
                if d_ist.date() == now_ist().date():
                    time_str = d_ist.strftime("%I:%M %p IST")
                else:
                    time_str = d_ist.strftime("%d %b %Y")
            except:
                time_str = str(pub)[:10]

        with st.container(border=True):
            meta = []
            if source:    meta.append(source.upper())
            if time_str:  meta.append(time_str)
            if meta:
                st.caption(" · ".join(meta))
            st.markdown(f"**{title}**")
            if content:
                st.write(content)
            if url:
                st.markdown(f"[Read full article ↗]({url})")


# ── AI Insight ────────────────────────────────────────────────────
def insight_button(articles, label, btn_key):
    if not get_key("SARVAM_API_KEY") or not articles:
        return
    if st.button("✦ Get AI Insight", key=btn_key):
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


# ── Word Intelligence ─────────────────────────────────────────────
def word_intelligence(articles, section_key):
    if not get_key("SARVAM_API_KEY"):
        st.caption("Add SARVAM_API_KEY for Word Intelligence.")
        return
    if not articles:
        return

    if st.button(
        "📚 Word Intelligence",
        key=f"wi_{section_key}",
        help="Extract 10 difficult words from this section"
    ):
        combined = " ".join(
            f"{(a.get('title','') or '')} "
            f"{(a.get('content','') or '')[:200]}"
            for a in articles[:10]
        )[:3000]

        with st.spinner("Extracting words…"):
            result = sarvam(
                f"Extract exactly 10 difficult English words from this text. "
                f"Return ONLY a valid JSON array, no markdown, no explanation:\n"
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
                words = json.loads(m.group())
                st.markdown("**📚 Difficult Words from This Section**")
                for i, w in enumerate(words[:10], 1):
                    with st.container(border=True):
                        st.markdown(f"**#{i} {w.get('word','').upper()}**")
                        st.write(f"📖 **Meaning:** {w.get('meaning','')}")
                        st.write(f"✏️ **Usage:** _{w.get('usage','')}_")
                        st.caption(f"💡 {w.get('description','')}")
            else:
                st.warning("Could not parse. Try again.")
        except json.JSONDecodeError:
            st.warning("Parse failed. Try again.")


# ════════════════════════════════════════════════════════════════
# HEADER
# ════════════════════════════════════════════════════════════════
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
        "Sports · Bihar · Samastipur · Rosera\n\n"
        "**Word Intelligence** available inside each section.\n\n"
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

# ── Smart filter ──────────────────────────────────────────────────
# Try 2 hours → fallback 6 hours → fallback 24 hours → show all
general_filtered, g_window = apply_smart_filter(
    general_raw,
    label="general",
    preferred_hours=2,
    fallback_hours=6,
    final_fallback_hours=24,
    min_count=4
)

regional_filtered, r_window = apply_smart_filter(
    regional_raw,
    label="regional",
    preferred_hours=6,       # Regional news less frequent
    fallback_hours=24,
    final_fallback_hours=72,
    min_count=2
)

# Show recency badge
def window_label(h):
    if h <= 2:    return "🟢 Last 2 hours"
    elif h <= 6:  return "🟡 Last 6 hours"
    elif h <= 24: return "🟠 Last 24 hours"
    elif h <= 72: return "🔴 Last 3 days"
    else:         return "⚪ All available"

st.caption(
    f"General: {window_label(g_window)}  ·  "
    f"Regional: {window_label(r_window)}"
)

general_raw  = general_filtered
regional_raw = regional_filtered

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
    arts = gen_cats.get("national", [])
    insight_button(arts, "India national", "ins_national")
    render_articles(arts)
    st.divider()
    word_intelligence(arts, "national")

with tab2:
    st.subheader("🌍 International News")
    arts = gen_cats.get("international", [])
    insight_button(arts, "world international", "ins_intl")
    render_articles(arts)
    st.divider()
    word_intelligence(arts, "intl")

with tab3:
    st.subheader("💰 Finance & Markets")
    arts = gen_cats.get("finance", [])
    insight_button(arts, "India finance and stock market", "ins_fin")
    render_articles(arts)
    st.divider()
    word_intelligence(arts, "finance")

with tab4:
    st.subheader("⚽ Sports")
    arts = gen_cats.get("sports", [])
    insight_button(arts, "India sports and cricket", "ins_sports")
    render_articles(arts)
    st.divider()
    word_intelligence(arts, "sports")

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
        word_intelligence(bihar, "bihar")
        st.divider()

    if sams:
        st.markdown("### Samastipur")
        render_articles(sams)
        st.divider()
        word_intelligence(sams, "samastipur")
        st.divider()

    if rosera:
        st.markdown("### Rosera")
        render_articles(rosera)
        st.divider()
        word_intelligence(rosera, "rosera")

    if not any([bihar, sams, rosera]):
        st.info(
            "No hyper-local results today. "
            "Bihar news may appear under National tab."
        )

st.divider()
st.caption(
    f"Bharat News AI · {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    f" · 2 credits/refresh"
)
