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

def clean_element(element):
    # Requirement 2: Clean junk links and menus, but keep bold/subheadings
    # Remove all a tags but keep their inner text
    for a_tag in element.find_all('a'):
        a_tag.unwrap()
    
    # Remove common junk elements
    for tag in element.find_all(['nav', 'footer', 'aside', 'script', 'style', 'button', 'form']):
        tag.decompose()

    # Further cleanup: remove elements with common junk classes or ids
    junk_keywords = ['share', 'social', 'menu', 'sidebar', 'newsletter', 'follow', 'related', 'promo']
    for tag in element.find_all(True):
        if tag.has_attr('class'):
            class_str = ' '.join(tag['class']).lower()
            if any(keyword in class_str for keyword in junk_keywords):
                tag.decompose()
                continue
        if tag.has_attr('id'):
            id_str = tag['id'].lower()
            if any(keyword in id_str for keyword in junk_keywords):
                tag.decompose()

def scrape_article_html(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find the main article body
        article_body = soup.find('article')
        if not article_body:
            # Fallback if no article tag
            article_body = soup.find('div', class_=lambda x: x and 'content' in x.lower())
            if not article_body:
                article_body = soup
        
        clean_element(article_body)
        
        # Collect headings and paragraphs
        elements = article_body.find_all(['p', 'h2', 'h3', 'h4'])
        content = ""
        for el in elements:
            html_el = str(el)
            # Rough length limit
            if len(content) + len(html_el) > 6000:
                break
            # Ignore empty or very short junk paragraphs
            if len(el.get_text(strip=True)) > 10:
                content += html_el
            
        return content
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

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
    
    # Requirement 4: Just Prova summary in bullet points, standard size, pure HTML
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
            
            # Requirement 1: Only 1 article per day
            for entry in parsed_feed.entries:
                link = entry.link
                title = entry.title
                pub_date = format_date(entry.get('published_parsed', entry.get('updated_parsed')))
                
                # Image Extraction Logic
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
                full_html = scrape_article_html(link)
                
                if len(full_html) > 200:
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
                    break # Stop after 1 valid article
            break # Stop after 1 feed
    
    bst_time = datetime.now(timezone.utc) + timedelta(hours=6)
    
    output = {
        "last_updated": bst_time.strftime("%d %b %Y, %I:%M %p"),
        "articles": news_data
    }
    
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
