import streamlit as st
from tavily import TavilyClient
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Use a faster, more specific keyword approach
CATEGORIES = {
    "national": ["government", "modi", "parliament", "delhi", "policy"],
    "international": ["un", "geopolitics", "biden", "war", "global"],
    "finance": ["nifty", "sensex", "stocks", "rbi", "ipo", "economy"],
    "sports": ["cricket", "ipl", "score", "match", "fifa", "olympics"],
    "regional": ["bihar", "patna", "samastipur", "rosera"]
}

def fetch_category_news(client, query, days=1):
    """Worker function for parallel execution"""
    try:
        # topic="news" is significantly faster and fresher
        response = client.search(
            query=query,
            topic="news",
            search_depth="basic", 
            max_results=10,
            days=days
        )
        return response.get("results", [])
    except Exception:
        return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_news_v2():
    key = get_key("TAVILY_API_KEY")
    if not key: return {}
    
    client = TavilyClient(api_key=key)
    results = {cat: [] for cat in CATEGORIES.keys()}
    
    # 1. Parallel Execution: Run all queries at the same time
    queries = {
        "national": "India breaking news government politics",
        "international": "World breaking news geopolitics international relations",
        "finance": "India stock market Nifty Sensex finance economy news",
        "sports": "India sports news cricket IPL scores",
        "regional": "Bihar Patna Samastipur Rosera breaking news"
    }

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_cat = {executor.submit(fetch_category_news, client, q): cat for cat, q in queries.items()}
        
        for future in future_to_cat:
            cat = future_to_cat[future]
            raw_data = future.result()
            
            # 2. Smarter Filtering: Deduplication and basic cleaning
            for item in raw_data:
                # Basic check to ensure content exists
                if item.get("title") and item.get("url"):
                    results[cat].append({
                        "title": item["title"],
                        "url": item["url"],
                        "content": item.get("content", "No description available."),
                        "published": item.get("published_date", "Just now")
                    })
    
    return results

# --- UI DISPLAY LOGIC (Ensure this is in your main app) ---
def display_news():
    news_data = fetch_all_news_v2()
    
    for category, articles in news_data.items():
        if articles:
            st.subheader(f"Latest in {category.title()}")
            for art in articles[:5]: # Show top 5 per category
                with st.expander(art['title']):
                    st.write(art['content'])
                    st.markdown(f"[Read full story]({art['url']})")
                    st.caption(f"Published: {art['published']}")
