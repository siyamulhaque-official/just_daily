import os
import json
import re
import html
import urllib.request
from datetime import datetime, timezone, timedelta
import feedparser

# DeepSeek API Configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
# স্ক্রিনশটের ডকুমেন্টেশন অনুযায়ী লেটেস্ট ফ্ল্যাশ মডেলটি ব্যবহার করা হলো
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
        system_prompt = "You are a professional journalistic editor summarizing public news for student readers."
        user_prompt = f"""
Summarize this news article in exactly 3 structured points.
**1. Core Concept:** (What happened in 1-2 concise sentences)
**2. Background:** (Key context)
**3. Importance & Impact:** (Why this matters)

Rules: Write strictly in pure ENGLISH. Never use Bengali. Do not add any introductory or concluding text.

Headline: {clean_title}
Details: {clean_context}
"""
    else:
        system_prompt = "তুমি একজন দক্ষ সংবাদ সম্পাদক। শিক্ষার্থীদের সহজে বোঝার জন্য সংবাদ সংক্ষেপ করো।"
        user_prompt = f"""
নিচের সংবাদটি ৩টি পয়েন্টে সংক্ষেপ করো:
**১. মূল ঘটনা বা Core Concept:** (১-২ বাক্যে)
**২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:** (কেন ঘটল)
**৩. এর প্রভাব বা গুরুত্ব:** (কেন জানা জরুরি)

নিয়ম: সম্পূর্ণ উত্তর শুদ্ধ বাংলায় লিখবে। কোনো ভূমিকা বা উপসংহার লিখবে না।

শিরোনাম: {clean_title}
বিষয়বস্তু: {clean_context}
"""

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3, # কম টেম্পারেচার দিলে টু-দ্য-পয়েন্ট এবং নির্ভুল উত্তর পাওয়া যায়
        "max_tokens": 800
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
        return clean_context[:200] + "..." if clean_context else "বিস্তারিত তথ্য মূল লিংকে উপলব্ধ।"

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key: 
        print("ত্রুটি: DEEPSEEK_API_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return

    articles = []
    print("DeepSeek-এর মাধ্যমে সংবাদ সংগ্রহ ও সামারি শুরু হচ্ছে...\n" + "=" * 50)

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
