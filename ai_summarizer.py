import os
import json
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from time import mktime

# API Configuration
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/chat/completions"

# Requirement 1: Only Tech & Innovation Feed (TechCrunch)
FEEDS = {
    "Tech & Innovation": [
        "https://techcrunch.com/feed/"
    ]
}

def generate_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def extract_clean_content(entry, link):
    raw_html = ""
    # 1. Try grabbing full content directly from feed (Fastest & ad-free)
    if 'content' in entry and len(entry.content) > 0:
        raw_html = entry.content[0].value
    elif 'description' in entry:
        raw_html = entry.description
        
    # 2. If feed text is too short, fallback to web scraping
    if len(raw_html) < 500:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(link, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            main_body = soup.find('div', class_='entry-content') or soup.find('article') or soup
            raw_html = str(main_body)
        except Exception as e:
            print(f"Scraping error: {e}")
            return ""

    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # Remove Links but keep text
    for a in soup.find_all('a'):
        a.unwrap()
        
    # Destroy unwanted structural tags
    for tag in soup.find_all(['nav', 'footer', 'aside', 'script', 'style', 'button', 'form', 'figure']):
        try:
            tag.decompose()
        except:
            pass
            
    # Destroy junk classes (Social, share, related) safely
    junk_keywords = ['share', 'social', 'newsletter', 'related', 'promo', 'jp-relatedposts']
    for tag in soup.find_all(True):
        if tag.has_attr('class'):
            class_str = ' '.join(tag['class']).lower()
            if any(keyword in class_str for keyword in junk_keywords):
                try:
                    tag.decompose()
                except:
                    pass

    # Extract ONLY pure paragraphs and headers
    final_content = ""
    for el in soup.find_all(['p', 'h2', 'h3', 'h4']):
        text = el.get_text(strip=True)
        if len(text) > 30:  # Skip tiny meaningless text blocks
            final_content += str(el)
            if len(final_content) > 6000:
                break
                
    return final_content

def format_date(parsed_time):
    if parsed_time:
        try:
            dt = datetime.fromtimestamp(mktime(parsed_time))
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return ""
    return ""

def summarize_with_deepseek(text):
    if not text or not DEEPSEEK_API_KEY:
        return "Summary not available."
    
    clean_text = BeautifulSoup(text, "html.parser").get_text()
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are 'Just Prova', an expert tech news editor. Analyze the article and provide a standard length summary. FORMAT REQUIREMENT: Start with a brief 1-2 sentence introduction, followed by exactly 3-4 bullet points highlighting the core event, background, and impact. You MUST use valid HTML tags (like <p>, <ul>, <li>, <strong>). NEVER use markdown (no **, #, etc.). The response must be pure, clean HTML ready to be injected into a webpage."
            },
            {
                "role": "user",
                "content": clean_text
            }
        ],
        "max_tokens": 400,
        "temperature": 0.5
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"API Error: {e}")
        return "<p>Failed to generate AI summary.</p>"

def main():
    news_data = []
    
    for category, urls in FEEDS.items():
        for feed_url in urls:
            parsed_feed = feedparser.parse(feed_url)
            
            for entry in parsed_feed.entries:
                link = entry.link
                title = entry.title
                pub_date = format_date(entry.get('published_parsed', entry.get('updated_parsed')))
                
                image = ""
                if 'media_content' in entry and len(entry.media_content) > 0:
                    image = entry.media_content[0].get('url', '')
                elif 'enclosures' in entry and len(entry.enclosures) > 0:
                    image = entry.enclosures[0].get('href', '')
                
                if not image:
                    html_content = entry.content[0].value if 'content' in entry else entry.get('description', '')
                    if html_content:
                        soup = BeautifulSoup(html_content, 'html.parser')
                        img_tag = soup.find('img')
                        if img_tag and img_tag.has_attr('src'):
                            image = img_tag['src']
                
                print(f"Processing: {title}")
                full_html = extract_clean_content(entry, link)
                
                # If valid content found, save and break
                if len(full_html) > 150:
                    summary = summarize_with_deepseek(full_html)
                    
                    news_data.append({
                        "id": generate_id(link),
                        "source": parsed_feed.feed.get('title', 'TechCrunch'),
                        "category": category,
                        "title": title,
                        "date": pub_date,
                        "link": link,
                        "image": image,
                        "full_text": full_html,
                        "summary": summary
                    })
                    break
            break
    
    bst_time = datetime.now(timezone.utc) + timedelta(hours=6)
    
    output = {
        "last_updated": bst_time.strftime("%d %b %Y, %I:%M %p"),
        "articles": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
