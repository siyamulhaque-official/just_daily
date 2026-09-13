import os
import json
import re
import html
import urllib.request
from datetime import datetime, timezone, timedelta
import feedparser
from bs4 import BeautifulSoup
import ssl

# SSL Certificate ইস্যু এড়ানোর জন্য
ssl._create_default_https_context = ssl._create_unverified_context

# DeepSeek API Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash" 

# শুধুমাত্র ইংলিশ গ্লোবাল নিউজ এবং টেক/আর্টিকেল প্ল্যাটফর্ম
RSS_FEEDS = [
    {"source": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "Global Affairs", "limit": 4},
    {"source": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "Global Affairs", "limit": 4},
    {"source": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "Tech & Innovation", "limit": 3},
    {"source": "Dev.to", "url": "https://dev.to/feed", "category": "Deep Reads", "limit": 3}
]

def clean_text(raw_html):
    if not raw_html: return ""
    no_tags = re.sub(r'<[^>]+>', '', raw_html)
    return html.unescape(no_tags).strip()

def extract_image(entry):
    """RSS থেকে ইমেজ এক্সট্র্যাক্ট করে"""
    if "media_content" in entry and entry.media_content:
        for media in entry.media_content:
            if "url" in media: return media["url"]
    if "media_thumbnail" in entry and entry.media_thumbnail:
        for media in entry.media_thumbnail:
            if "url" in media: return media["url"]
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image") or "url" in enc:
                return enc.get("url") or enc.get("href")
    desc = entry.get("summary", "") + entry.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if match: return match.group(1)
    return ""

def fetch_full_article_text(url):
    """মূল ওয়েবসাইটে ঢুকে সম্পূর্ণ আর্টিকেলটি স্ক্র্যাপ করে আনে"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html_content = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(html_content, 'html.parser')

        # অপ্রয়োজনীয় ট্যাগগুলো (স্ক্রিপ্ট, অ্যাড, স্টাইল) বাদ দেওয়া
        for script in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
            script.extract()

        # আর্টিকেলের সব প্যারাগ্রাফ <p> ট্যাগ থেকে সংগ্রহ করা
        paragraphs = soup.find_all('p')
        text_blocks = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
        
        full_text = '\n\n'.join(text_blocks)
        
        # DeepSeek-এর টোকেন বাঁচাতে টেক্সট সাইজ ৫০০০ ক্যারেক্টারে লিমিট করা
        if len(full_text) > 5000:
            full_text = full_text[:5000] + "...\n[Read more on the source link]"
            
        return full_text
    except Exception as e:
        print(f"    [!] স্ক্র্যাপিং ফেইলড ({url}): {e}")
        return ""

def generate_summary_deepseek(api_key, title, full_text):
    """DeepSeek দিয়ে আর্টিকেলের ওপর বেস করে ডাইনামিক সামারি তৈরি করে"""
    system_prompt = "You are a professional journalistic editor providing clear, natural, and comprehensive news summaries."
    user_prompt = f"""
Summarize this news article so it is easily understandable.
Read the full text and extract the most important information. Do not force a specific length. Use exactly as much text and as many points as needed to properly explain the news.

Structure the response naturally. You may include:
- The core event (What happened)
- Important background or details
- The impact or why it matters

Rules:
- Write strictly in pure ENGLISH.
- Use bold text (`**Heading:**`) for the key points so it looks visually structured.
- Do not write generic intros or pleasantries.

Headline: {title}
Full Article Text: {full_text}
"""

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 1000
    }

    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(data).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"    [!] DeepSeek API Error: {e}")
        return "Summary could not be generated at this time."

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key: 
        print("ত্রুটি: DEEPSEEK_API_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return

    articles = []
    print("সংবাদ সংগ্রহ, স্ক্র্যাপিং ও সামারাইজেশন শুরু হচ্ছে...\n" + "=" * 50)

    for feed_info in RSS_FEEDS:
        print(f"\n[{feed_info['source']}] স্ক্যান করা হচ্ছে...")
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:feed_info["limit"]]:
                clean_title = clean_text(entry.get("title", "No Title"))
                link = entry.get("link", "#").strip()
                image_url = extract_image(entry)

                print(f"-> প্রসেসিং: {clean_title[:40]}...")
                
                # ১. মূল ওয়েবসাইট থেকে ফুল টেক্সট স্ক্র্যাপ করা
                full_article_text = fetch_full_article_text(link)
                
                # যদি ফুল টেক্সট স্ক্র্যাপ করতে না পারে, তবে আরএসএস এর ডিফল্ট সামারি নেবে
                if not full_article_text or len(full_article_text) < 100:
                    full_article_text = clean_text(entry.get("summary", entry.get("description", "")))
                
                # ২. DeepSeek দিয়ে সামারি তৈরি করা
                ai_brief = generate_summary_deepseek(api_key, clean_title, full_article_text)

                articles.append({
                    "category": feed_info["category"],
                    "source": feed_info["source"],
                    "title": clean_title,
                    "link": link,
                    "image": image_url,
                    "full_text": full_article_text, # নতুন ফিল্ড: ফ্রন্টএন্ডে পড়ার জন্য
                    "summary": ai_brief             # এআই সামারি
                })
        except Exception as err:
            print(f"Error ({feed_info['source']}): {err}")

    bd_time = datetime.now(timezone(timedelta(hours=6)))
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": bd_time.strftime("%Y-%m-%d %I:%M %p"), "articles": articles}, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"সফলভাবে মোট {len(articles)}টি ফুল আর্টিকেল ও সামারি আপডেট করা হয়েছে!")

if __name__ == "__main__":
    main()
