import os
import json
import re
import html
from datetime import datetime, timezone, timedelta
import feedparser

try:
    from google import genai
    from google.genai import types
    USING_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as genai
        USING_NEW_SDK = False
    except ImportError:
        raise ImportError("Gemini SDK পাওয়া যায়নি! pip install google-genai রান করুন।")

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

def generate_summary(api_key, title, context, lang):
    clean_context = clean_text(context)
    clean_title = clean_text(title)

    prompt = f"""
Summarize this news article in exactly 3 structured points.
**1. Core Concept:** (What happened in 1-2 concise sentences)
**2. Background:** (Key context)
**3. Importance & Impact:** (Why this matters)

Rules: Write strictly in pure {'ENGLISH. Never use Bengali.' if lang == 'en' else 'BENGALI. Never use English.'}
Title: {clean_title}
Details: {clean_context}
""" if lang == 'en' else f"""
শিক্ষার্থীদের সহজে বোঝার জন্য নিচের সংবাদটি ৩টি পয়েন্টে সংক্ষেপ করো:
**১. মূল ঘটনা বা Core Concept:** (১-২ বাক্যে)
**২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:** (কেন ঘটল)
**৩. এর প্রভাব বা গুরুত্ব:** (কেন জানা জরুরি)

নিয়ম: সম্পূর্ণ উত্তর শুদ্ধ বাংলায় লিখবে। কোনো ভূমিকা লিখবে না।
শিরোনাম: {clean_title}
বিষয়বস্তু: {clean_context}
"""

    try:
        if USING_NEW_SDK:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE")
                ]
            )
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
            return res.text.strip()
        else:
            genai.configure(api_key=api_key)
            safety = [
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}
            ]
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt, safety_settings=safety)
            return res.text.strip()
    except Exception as e:
        print(f"API Error ({clean_title[:15]}): {e}")
        return clean_context[:200] + "..." if clean_context else "বিস্তারিত তথ্য মূল লিংকে উপলব্ধ।"

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return

    articles = []
    print("সংবাদ সংগ্রহ শুরু হচ্ছে...\n" + "=" * 50)

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:feed_info["limit"]]:
                clean_title = clean_text(entry.get("title", "No Title"))
                link = entry.get("link", "#").strip()
                summary_raw = entry.get("summary", entry.get("description", ""))
                image_url = extract_image(entry)

                print(f"-> প্রসেসিং: {clean_title[:30]}...")
                ai_brief = generate_summary(api_key, clean_title, summary_raw, feed_info["lang"])

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
