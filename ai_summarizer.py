import os
import json
import re
import html
from datetime import datetime, timezone, timedelta
import feedparser
from google import genai

# সক্রিয় ও লাইভ আরএসএস ফিড (বাংলা ও ইংরেজি মিলিয়ে মোট ১২টি সংবাদ)
RSS_FEEDS = [
    {
        "source": "প্রথম আলো",
        "url": "https://www.prothomalo.com/feed",
        "lang": "bn",
        "limit": 4
    },
    {
        "source": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "lang": "en",
        "limit": 4
    },
    {
        "source": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "lang": "en",
        "limit": 4
    }
]

def clean_text(raw_html):
    """HTML ট্যাগ এবং এনটিটি মুছে একদম নির্ভেজাল টেক্সট তৈরি করে"""
    if not raw_html:
        return ""
    no_tags = re.sub(r'<[^>]+>', '', raw_html)
    return html.unescape(no_tags).strip()

def extract_image(entry):
    """নিউজ ফিড থেকে আসল ছবি বের করে আনার লজিক"""
    # ১. media_content
    if "media_content" in entry and entry.media_content:
        for media in entry.media_content:
            if "url" in media:
                return media["url"]

    # ২. media_thumbnail (BBC)
    if "media_thumbnail" in entry and entry.media_thumbnail:
        for media in entry.media_thumbnail:
            if "url" in media:
                return media["url"]

    # ৩. enclosures
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image") or "url" in enc:
                return enc.get("url") or enc.get("href")

    # ৪. Description-এর ভেতরে লুকানো <img> ট্যাগ
    desc = entry.get("summary", "") + entry.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if match:
        return match.group(1)

    return None

def generate_summary(client, title, context, lang):
    clean_context = clean_text(context)
    clean_title = clean_text(title)

    if lang == "en":
        prompt = f"""
You are a professional journalistic editor summarizing public news for student readers.
Provide an objective, structured summary in exactly 3 points:
**1. Core Concept:** (What happened in 1-2 concise sentences)
**2. Background:** (Key context and underlying factors)
**3. Importance & Impact:** (Why this matters globally or to readers)

Rules:
- Write strictly in pure ENGLISH. Never use Bengali for this text.
- Maintain a neutral journalistic tone.
- Do not add intros or conclusions.

Headline: {clean_title}
Details: {clean_context}
"""
    else:
        prompt = f"""
তুমি একজন দক্ষ সংবাদ সম্পাদক। শিক্ষার্থীদের সহজে বোঝার জন্য নিচের সংবাদটি ৩টি পয়েন্টে সংক্ষেপ করো:
**১. মূল ঘটনা বা Core Concept:** (সংক্ষিপ্ত ১-২ বাক্যে)
**২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:** (কেন ঘটনাটি ঘটল)
**৩. এর প্রভাব বা গুরুত্ব:** (শিক্ষার্থীদের কেন এটি জানা জরুরি)

নিয়ম:
- সম্পূর্ণ উত্তরটি শুদ্ধ ও প্রাঞ্জল বাংলায় লিখবে। কোনো ইংরেজি অনুবাদ করবে না।
- কোনো ভূমিকা বা উপসংহার ছাড়া সরাসরি ৩টি পয়েন্ট লিখবে।

শিরোনাম: {clean_title}
বিষয়বস্তু: {clean_context}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"এআই সামারি তৈরিতে সতর্কবার্তা: {e}")
        return clean_context[:200] + "..." if clean_context else "বিস্তারিত তথ্য মূল লিংকে উপলব্ধ।"

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ত্রুটি: GEMINI_API_KEY পাওয়া যায়নি!")
        return

    client = genai.Client(api_key=api_key)
    articles = []

    print("সংবাদ সংগ্রহ শুরু হচ্ছে...\n" + "=" * 50)

    for feed_info in RSS_FEEDS:
        print(f"[{feed_info['source']}] স্ক্যান করা হচ্ছে...")
        try:
            feed = feedparser.parse(feed_info["url"])
            entries = feed.entries[:feed_info["limit"]]

            for entry in entries:
                raw_title = entry.get("title", "No Title")
                clean_title = clean_text(raw_title)
                link = entry.get("link", "#").strip()
                summary_raw = entry.get("summary", entry.get("description", ""))
                image_url = extract_image(entry)

                print(f"-> প্রসেসিং: {clean_title[:35]}... (ছবি: {'হ্যাঁ' if image_url else 'না'})")
                ai_brief = generate_summary(client, clean_title, summary_raw, feed_info["lang"])

                articles.append({
                    "source": feed_info["source"],
                    "title": clean_title,
                    "link": link,
                    "image": image_url,
                    "summary": ai_brief
                })
        except Exception as err:
            print(f"ফিড এরর ({feed_info['source']}): {err}")

    # বাংলাদেশ সময় (UTC+6)
    bd_time = datetime.now(timezone(timedelta(hours=6)))
    last_updated_str = bd_time.strftime("%Y-%m-%d %I:%M %p")

    data = {
        "last_updated": last_updated_str,
        "articles": articles
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nসফলভাবে মোট {len(articles)}টি সংবাদ 'news.json'-এ সংরক্ষিত হয়েছে!")

if __name__ == "__main__":
    main()
