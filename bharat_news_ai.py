import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional
from collections import defaultdict
import re

# ============ Streamlit Configuration ============
st.set_page_config(
    page_title="🗞️ Indian News Dashboard",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ Custom CSS ============
st.markdown("""
<style>
    :root {
        --primary: #FF9933;
        --secondary: #138808;
        --accent: #1D3557;
    }
    
    .header-main {
        background: linear-gradient(135deg, #FF9933 0%, #1D3557 100%);
        color: white;
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .header-main h1 {
        font-size: 2.8rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin: 0;
    }
    
    .header-main p {
        font-size: 1rem;
        opacity: 0.95;
        margin-top: 0.5rem;
    }
    
    .category-header {
        background: linear-gradient(90deg, #FF9933 0%, #FFB366 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-top: 2rem;
        margin-bottom: 1.5rem;
        border-left: 5px solid #1D3557;
        font-weight: 700;
        font-size: 1.3rem;
    }
    
    .region-header {
        background: linear-gradient(90deg, #138808 0%, #1D3557 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 5px solid #FF9933;
        font-weight: 700;
        font-size: 1.2rem;
    }
    
    .news-card {
        background: white;
        border: 1px solid #E8E8E8;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.2rem;
        border-left: 4px solid #FF9933;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
    }
    
    .news-card:hover {
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    .news-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1D3557;
        margin-bottom: 0.8rem;
        line-height: 1.4;
    }
    
    .news-source {
        font-size: 0.85rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .news-snippet {
        font-size: 0.95rem;
        color: #333;
        line-height: 1.6;
    }
    
    .word-section {
        background: linear-gradient(135deg, #F8F9FA 0%, #EFF6FF 100%);
        border-radius: 14px;
        padding: 2rem;
        margin-top: 2.5rem;
        border: 1px solid #E0E7FF;
    }
    
    .word-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.2rem;
        border-left: 4px solid #138808;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    
    .word-text {
        font-size: 1.25rem;
        font-weight: 800;
        color: #138808;
        margin-bottom: 0.5rem;
    }
    
    .word-meaning {
        font-size: 0.95rem;
        color: #333;
        margin-bottom: 1rem;
        padding: 1rem;
        background-color: #F0F8F0;
        border-radius: 8px;
        border-left: 3px solid #138808;
    }
    
    .word-usage {
        font-size: 0.9rem;
        color: #555;
        font-style: italic;
        padding: 1rem;
        background-color: #FFF9F0;
        border-radius: 8px;
        margin-bottom: 1rem;
        border-left: 3px solid #FF9933;
    }
    
    .word-description {
        font-size: 0.9rem;
        color: #444;
        line-height: 1.7;
    }
    
    .empty-state {
        text-align: center;
        padding: 2rem;
        color: #666;
    }
    
    .stat-box {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #FF9933;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    
    .stat-number {
        font-size: 2rem;
        font-weight: 800;
        color: #FF9933;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# ============ API Configuration ============
TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", "")
SARVAM_API_KEY = st.secrets.get("SARVAM_API_KEY", "")

# ============ Helper Functions ============

@st.cache_data(ttl=3600)
def fetch_all_news_single_call(days: int = 3, max_results: int = 25) -> list:
    """
    🎯 OPTIMIZED: Single Tavily API call for ALL news categories
    One call fetches national, international, finance, sports, and regional news
    """
    if not TAVILY_API_KEY:
        st.error("❌ TAVILY_API_KEY not found in secrets")
        return []
    
    try:
        # Comprehensive single query covering all categories
        query = (
            "India national news OR international news OR "
            "NSE BSE stock market finance news OR "
            "cricket IPL sports India OR "
            "Bihar Samastipur Rosera news"
        )
        
        url = "https://api.tavily.com/search"
        
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "include_images": True,
            "max_results": max_results,
            "days": days
        }
        
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get("results", [])
        
        return articles
    
    except Exception as e:
        st.error(f"❌ API Error: {str(e)}")
        return []


def categorize_news(articles: list) -> dict:
    """Categorize articles into different news types"""
    
    keywords_map = {
        "national": ["india", "indian", "bharatiya", "national", "country", "govt", "government"],
        "international": ["world", "global", "international", "usa", "uk", "europe", "china", "asia"],
        "finance": ["market", "stock", "nse", "bse", "finance", "economic", "rupee", "budget", "trade", "share", "investing"],
        "sports": ["cricket", "ipl", "sports", "match", "game", "player", "olympic", "football", "team"],
        "bihar": ["bihar", "patna", "बिहार", "पटना"],
        "samastipur": ["samastipur", "समस्तीपुर"],
        "rosera": ["rosera", "रोसेरा"],
    }
    
    categorized = defaultdict(list)
    
    for article in articles:
        title = article.get("title", "").lower()
        content = article.get("content", "").lower()
        full_text = title + " " + content
        
        found = False
        for category, keywords in keywords_map.items():
            if any(kw in full_text for kw in keywords):
                categorized[category].append(article)
                found = True
                if category not in ["bihar", "samastipur", "rosera"]:
                    break
        
        if not found:
            categorized["general"].append(article)
    
    return dict(categorized)


def analyze_words_with_sarvam(news_content: str) -> Optional[dict]:
    """Extract 10 difficult words using Sarvam AI"""
    if not SARVAM_API_KEY:
        return None
    
    try:
        url = "https://api.sarvam.ai/v2/completion"
        
        prompt = f"""Extract exactly 10 difficult/challenging English words from this news. 
Return ONLY valid JSON array with objects containing: word, meaning, usage, description
No markdown, no backticks, just pure JSON.

News: {news_content[:2000]}"""
        
        headers = {
            "Authorization": f"Bearer {SARVAM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "Sarvam-2-Bolt",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 2000
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Extract JSON
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            words_data = json.loads(json_match.group())
            return {"words": words_data[:10]}
        
        return None
    
    except Exception as e:
        st.warning(f"⚠️ Sarvam Error: {str(e)}")
        return None


# ============ Main Dashboard ============

# Header
st.markdown("""
<div class="header-main">
    <h1>🇮🇳 Indian News Dashboard</h1>
    <p>Real-time news in 1 API call | Word Intelligence Analysis | Streamlit Cloud Ready</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ Dashboard Settings")
    st.info("✅ Optimized: 1 Tavily call per session | Deploy ready")
    
    news_days = st.slider("News recency (days)", 1, 7, 3)
    max_articles = st.slider("Articles to fetch", 15, 30, 25)
    
    st.divider()
    st.markdown("**📌 Configuration**")
    st.text("Tavily API: Cached for 1 hour")
    st.text("Sarvam AI: Optional word analysis")

# Fetch news with single API call
st.markdown("🔄 Fetching news...", help="Single Tavily API call")
all_news = fetch_all_news_single_call(days=news_days, max_results=max_articles)

if not all_news:
    st.warning("⚠️ No news fetched. Check your Tavily API key in secrets.")
    st.stop()

# Categorize news
categorized = categorize_news(all_news)

# Stats
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="stat-box">
        <div class="stat-number">{len(categorized.get('national', []))}</div>
        <div class="stat-label">🏠 National</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-box">
        <div class="stat-number">{len(categorized.get('international', []))}</div>
        <div class="stat-label">🌍 International</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-box">
        <div class="stat-number">{len(categorized.get('finance', []))}</div>
        <div class="stat-label">💰 Finance</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-box">
        <div class="stat-number">{len(categorized.get('sports', []))}</div>
        <div class="stat-label">⚽ Sports</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 National",
    "🌍 International",
    "💰 Finance",
    "⚽ Sports",
    "📍 Regional",
    "📚 Words"
])

# Tab 1: National
with tab1:
    st.markdown('<div class="category-header">🏠 National News</div>', unsafe_allow_html=True)
    national = categorized.get("national", [])
    
    if national:
        for idx, article in enumerate(national[:8]):
            st.markdown(f"""
            <div class="news-card">
                <div class="news-source">{article.get('source', 'Unknown')}</div>
                <div class="news-title">{article.get('title', 'No title')}</div>
                <div class="news-snippet">{article.get('content', '')[:280]}...</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">📭 No national news found</div>', unsafe_allow_html=True)

# Tab 2: International
with tab2:
    st.markdown('<div class="category-header">🌍 International News</div>', unsafe_allow_html=True)
    intl = categorized.get("international", [])
    
    if intl:
        for article in intl[:8]:
            st.markdown(f"""
            <div class="news-card">
                <div class="news-source">{article.get('source', 'Unknown')}</div>
                <div class="news-title">{article.get('title', 'No title')}</div>
                <div class="news-snippet">{article.get('content', '')[:280]}...</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">📭 No international news found</div>', unsafe_allow_html=True)

# Tab 3: Finance
with tab3:
    st.markdown('<div class="category-header">💰 Finance & Markets</div>', unsafe_allow_html=True)
    finance = categorized.get("finance", [])
    
    if finance:
        for article in finance[:8]:
            st.markdown(f"""
            <div class="news-card">
                <div class="news-source">{article.get('source', 'Unknown')}</div>
                <div class="news-title">{article.get('title', 'No title')}</div>
                <div class="news-snippet">{article.get('content', '')[:280]}...</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">📭 No finance news found</div>', unsafe_allow_html=True)

# Tab 4: Sports
with tab4:
    st.markdown('<div class="category-header">⚽ Sports News</div>', unsafe_allow_html=True)
    sports = categorized.get("sports", [])
    
    if sports:
        for article in sports[:8]:
            st.markdown(f"""
            <div class="news-card">
                <div class="news-source">{article.get('source', 'Unknown')}</div>
                <div class="news-title">{article.get('title', 'No title')}</div>
                <div class="news-snippet">{article.get('content', '')[:280]}...</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">📭 No sports news found</div>', unsafe_allow_html=True)

# Tab 5: Regional
with tab5:
    st.markdown('<div class="category-header">📍 Regional News</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="region-header">🗺️ Bihar</div>', unsafe_allow_html=True)
        bihar = categorized.get("bihar", [])
        if bihar:
            for article in bihar[:5]:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-source">{article.get('source', 'Unknown')}</div>
                    <div class="news-title">{article.get('title', 'No title')}</div>
                    <div class="news-snippet">{article.get('content', '')[:150]}...</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">📭 No Bihar news</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="region-header">📍 Samastipur</div>', unsafe_allow_html=True)
        samastipur = categorized.get("samastipur", [])
        if samastipur:
            for article in samastipur[:5]:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-source">{article.get('source', 'Unknown')}</div>
                    <div class="news-title">{article.get('title', 'No title')}</div>
                    <div class="news-snippet">{article.get('content', '')[:150]}...</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">📭 No Samastipur news</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="region-header">📍 Rosera</div>', unsafe_allow_html=True)
        rosera = categorized.get("rosera", [])
        if rosera:
            for article in rosera[:5]:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-source">{article.get('source', 'Unknown')}</div>
                    <div class="news-title">{article.get('title', 'No title')}</div>
                    <div class="news-snippet">{article.get('content', '')[:150]}...</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">📭 No Rosera news</div>', unsafe_allow_html=True)

# Tab 6: Word Intelligence
with tab6:
    st.markdown('<div class="word-section">', unsafe_allow_html=True)
    st.markdown('## 📚 10 Difficult Words from Today\'s News')
    
    if st.button("🔍 Analyze Words with Sarvam AI", key="analyze_btn"):
        # Combine news content
        combined = " ".join([
            f"{a.get('title', '')} {a.get('content', '')}"
            for a in all_news[:15]
        ])
        
        if combined:
            with st.spinner("🤖 Analyzing with Sarvam AI..."):
                result = analyze_words_with_sarvam(combined)
            
            if result:
                words_list = result.get("words", [])
                
                if words_list:
                    for idx, word_item in enumerate(words_list, 1):
                        st.markdown(f"""
                        <div class="word-card">
                            <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                                <span style="font-size: 24px; color: #FF9933;">#{idx}</span>
                                <div class="word-text">{word_item.get('word', 'Unknown')}</div>
                            </div>
                            
                            <div style="margin-bottom: 15px;">
                                <strong style="color: #1D3557;">📖 Meaning:</strong>
                                <div class="word-meaning">{word_item.get('meaning', '')}</div>
                            </div>
                            
                            <div style="margin-bottom: 15px;">
                                <strong style="color: #1D3557;">📰 Usage:</strong>
                                <div class="word-usage">"{word_item.get('usage', '')}"</div>
                            </div>
                            
                            <div>
                                <strong style="color: #1D3557;">💡 Description:</strong>
                                <div class="word-description">{word_item.get('description', '')}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if idx < len(words_list):
                            st.divider()
                else:
                    st.warning("⚠️ Could not extract words")
            else:
                st.error("❌ Word analysis failed. Check Sarvam API key.")
        else:
            st.warning("⚠️ No news content available")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.divider()
st.markdown(f"""
<div style="text-align: center; color: #666; font-size: 0.9rem; padding: 1rem;">
    <p>🇮🇳 Indian News Dashboard | Powered by Tavily & Sarvam AI</p>
    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Data cached for 1 hour</p>
</div>
""", unsafe_allow_html=True)
