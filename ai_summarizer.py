import os
import json
import re
import html
import urllib.request
from datetime import datetime, timezone, timedelta
import feedparser

# DeepSeek API Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-flash" 

RSS_FEEDS = [
    {"source": "প্রথম আলো", "url": "https://www.prothomalo.com/feed", "lang": "bn", "limit": 4},
    {"source": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "lang": "en", "limit": 4},
    {"source": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "lang": "en", "limit": 4}
]

def clean_text(raw_html):
    if not raw_html: return ""
    no_tags = re.sub(r'<[^>]+>', '', raw_html)
    return html.unescape(no_tags).strip()

def extract_image(entry):
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
    return None

def generate_summary_deepseek(api_key, title, context, lang):
    clean_context = clean_text(context)
    clean_title = clean_text(title)

    if lang == 'en':
        system_prompt = "You are a professional journalistic editor providing clear, natural, and comprehensive news summaries."
        user_prompt = f"""
Summarize this news article so it is easily understandable.
Do not force a specific length. Use exactly as much text and as many points as needed to properly explain the news. 

Structure the response naturally. You may include:
- The core event (What happened)
- Important background or details
- The impact or why it matters

Rules:
- Write strictly in pure ENGLISH. Never use Bengali.
- Use bold text (`**Heading:**`) for the key points so it looks visually structured.
- Make it flow naturally based on the depth of the specific news article.

Headline: {clean_title}
Details: {clean_context}
"""
    else:
        system_prompt = "তুমি একজন দক্ষ সংবাদ সম্পাদক। তুমি পাঠকদের সহজে বোঝার জন্য ন্যাচারালভাবে সংবাদ সংক্ষেপ করো।"
        user_prompt = f"""
নিচের সংবাদটি সাধারণ পাঠকদের সহজে বোঝার জন্য সংক্ষেপ করো।
সংবাদটি পরিষ্কারভাবে বোঝাতে যতটুকু ব্যাখ্যা এবং যতগুলো পয়েন্ট দরকার, ঠিক ততটুকুই ব্যবহার করবে। কোনো নির্দিষ্ট লাইন বা পয়েন্টের বাধ্যবাধকতা নেই, খবরের গুরুত্ব অনুযায়ী স্বাভাবিকভাবে লিখবে।

প্রয়োজন অনুযায়ী নিচের বিষয়গুলো কভার করবে:
- মূল ঘটনা (কী ঘটেছে)
- পেছনের কারণ বা বিস্তারিত তথ্য
- এর প্রভাব বা গুরুত্ব

নিয়ম:
- সম্পূর্ণ উত্তর শুদ্ধ ও প্রাঞ্জল বাংলায় লিখবে। কোনো ইংরেজি ব্যবহার করবে না।
- পয়েন্টগুলোর নাম অবশ্যই বোল্ড (`**পয়েন্টের নাম:**`) করে দেবে যাতে দেখতে সুন্দর লাগে।
- কোনো অপ্রয়োজনীয় ভূমিকা বা উপসংহার লিখবে না।

শিরোনাম: {clean_title}
বিষয়বস্তু: {clean_context}
"""

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3, # টেম্পারেচার আবার কমানো হয়েছে যাতে অতিরিক্ত কথা না বলে একদম টু-দ্য-পয়েন্ট থাকে
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
        print(f"DeepSeek API Error ({clean_title[:15]}): {e}")
        return clean_context[:300] + "..." if clean_context else "বিস্তারিত তথ্য মূল লিংকে উপলব্ধ।"

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key: 
        print("ত্রুটি: DEEPSEEK_API_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return

    articles = []
    print("DeepSeek-এর মাধ্যমে সংবাদ সংগ্রহ ও ন্যাচারাল সামারি শুরু হচ্ছে...\n" + "=" * 50)

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:feed_info["limit"]]:
                clean_title = clean_text(entry.get("title", "No Title"))
                link = entry.get("link", "#").strip()
                summary_raw = entry.get("summary", entry.get("description", ""))
                image_url = extract_image(entry)

                print(f"-> প্রসেসিং: {clean_title[:30]}...")
                ai_brief = generate_summary_deepseek(api_key, clean_title, summary_raw, feed_info["lang"])

                articles.append({
                    "source": feed_info["source"],
                    "title": clean_title,
                    "link": link,
                    "image": image_url,
                    "summary": ai_brief
                })
        except Exception as err:
            print(f"Error ({feed_info['source']}): {err}")

    bd_time = datetime.now(timezone(timedelta(hours=6)))
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": bd_time.strftime("%Y-%m-%d %I:%M %p"), "articles": articles}, f, ensure_ascii=False, indent=2)
    print("আপডেট সম্পন্ন!")

if __name__ == "__main__":
    main()
