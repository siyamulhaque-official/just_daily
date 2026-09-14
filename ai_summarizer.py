import os
import json
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# API Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"

FEEDS = {
    "Global Affairs": [
        "http://www.aljazeera.com/xml/rss/all.xml",
        "http://feeds.bbci.co.uk/news/world/rss.xml"
    ],
    "Tech & Innovation": [
        "https://techcrunch.com/feed/"
    ],
    "Deep Reads": [
        "https://dev.to/feed"
    ]
}

def generate_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def scrape_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text from paragraphs
        paragraphs = soup.find_all('p')
        full_text = ' '.join([p.get_text(strip=True) for p in paragraphs])
        
        # Clean and limit to 5000 characters
        return full_text[:5000]
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def summarize_with_deepseek(text):
    if not text or not DEEPSEEK_API_KEY:
        return "Summary not available."
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-flash",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert news editor. Generate a dynamic, highly professional summary in pure ENGLISH based on the provided text. Dynamically highlight key aspects (Core event, background, impact) naturally."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "max_tokens": 300,
        "temperature": 0.5
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"API Error: {e}")
        return "Failed to generate AI summary."

def main():
    news_data = []
    
    for category, urls in FEEDS.items():
        for feed_url in urls:
            parsed_feed = feedparser.parse(feed_url)
            # Process top 3 entries per feed to save time/tokens
            for entry in parsed_feed.entries[:3]:
                link = entry.link
                title = entry.title
                
                # Check for image
                image = ""
                if hasattr(entry, 'media_content') and len(entry.media_content) > 0:
                    image = entry.media_content[0].get('url', '')
                elif hasattr(entry, 'links'):
                    for item in entry.links:
                        if 'image' in item.get('type', ''):
                            image = item.get('href', '')
                
                print(f"Processing: {title}")
                full_text = scrape_article_text(link)
                
                if len(full_text) > 200: # Ensure valid content
                    summary = summarize_with_deepseek(full_text)
                    
                    news_data.append({
                        "id": generate_id(link),
                        "source": parsed_feed.feed.get('title', category),
                        "category": category,
                        "title": title,
                        "link": link,
                        "image": image,
                        "full_text": full_text,
                        "summary": summary
                    })
    
    # BST (+6 UTC) Timestamp
    bst_time = datetime.now(timezone.utc) + timedelta(hours=6)
    
    output = {
        "last_updated": bst_time.strftime("%Y-%m-%d %I:%M %p BST"),
        "articles": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
