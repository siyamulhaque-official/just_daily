import os
import json
import re
from datetime import datetime, timezone, timedelta
import feedparser

try:
    from google import genai
    USING_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as genai
        USING_NEW_SDK = False
    except ImportError:
        raise ImportError("Gemini SDK পাওয়া যায়নি! pip install google-genai রান করুন।")

RSS_FEEDS = [
    {
        "source": "প্রথম আলো",
        "url": "https://www.prothomalo.com/feed",
        "lang": "bn",
        "limit": 4
    },
    {
        "source": "The Daily Star",
        "url": "https://www.thedailystar.net/frontpage/rss.xml",
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

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        try:
            import config
            key = getattr(config, "GEMINI_API_KEY", None)
        except ImportError:
            pass
    return key

def extract_image(entry):
    """
    বিভিন্ন আরএসএস ফিডের ট্যাগ বিশ্লেষণ করে খবরের মূল ব্যানার ছবি বের করে
    """
    # ১. media_content ট্যাগ চেক
    if "media_content" in entry and entry.media_content:
        for media in entry.media_content:
            if "url" in media:
                return media["url"]

    # ২. media_thumbnail ট্যাগ চেক (যেমন: BBC)
    if "media_thumbnail" in entry and entry.media_thumbnail:
        for media in entry.media_thumbnail:
            if "url" in media:
                return media["url"]

    # ৩. enclosures ট্যাগ চেক (যেমন: Daily Star)
    if "enclosures" in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image") or "url" in enc:
                return enc.get("url") or enc.get("href")

    # ৪. summary বা description-এর ভেতরের <img> ট্যাগ থেকে খোঁজা
    content_raw = entry.get("summary", "") + entry.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_raw)
    if match:
        return match.group(1)

    return None

def clean_html(raw_html):
    """HTML ট্যাগ মুছে সাধারণ টেক্সট তৈরি করে"""
    return re.sub(r'<[^>]+>', ' ', raw_html).strip()

def call_gemini(api_key, prompt):
    if USING_NEW_SDK:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()

def generate_summary(api_key, title, context_text, lang):
    clean_context = clean_html(context_text)

    if lang == "en":
        prompt = f"""
You are an expert news editor. Summarize the following news article for high school and college students into exactly 3 structured points.

STRICT RULES:
1. Write 100% in pure ENGLISH. Absolutely DO NOT translate to Bengali.
2. Use the exact bullet format:
**1. Core Concept:** (What happened in 1-2 clear sentences)
**2. Background:** (Why it happened / key context)
**3. Importance & Impact:** (Why readers/students should care)
3. Do not include any introductory or concluding text.

Headline: {title}
Context: {clean_context}
"""
    else:
        prompt = f"""
তুমি একজন দক্ষ সংবাদ সম্পাদক। শিক্ষার্থীদের সহজে বোঝার জন্য নিচের সংবাদটি ৩টি পয়েন্টে সংক্ষেপ করো।

নিয়ম:
১. সম্পূর্ণ উত্তরটি শুদ্ধ বাংলায় লিখবে। কোনো ইংরেজি অনুবাদ করবে না।
২. হুবহু এই ফরম্যাটটি ব্যবহার করবে:
**১. মূল ঘটনা বা Core Concept:** (সংক্ষিপ্ত ১-২ বাক্যে)
**২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:** (কেন ঘটনাটি ঘটল)
**৩. এর প্রভাব বা গুরুত্ব:** (শিক্ষার্থীদের কেন এটি জানা জরুরি)
৩. কোনো ভূমিকা বা উপসংহার লিখবে না।

শিরোনাম: {title}
বিষয়বস্তু: {clean_context}
"""

    try:
        return call_gemini(api_key, prompt)
    except Exception as e:
        print(f"এআই সামারি তৈরিতে এরর: {e}")
        return clean_context[:180] + "..." if clean_context else "বিস্তারিত তথ্য পাওয়া যায়নি।"

def main():
    api_key = get_api_key()
    if not api_key:
        print("ত্রুটি: GEMINI_API_KEY পাওয়া যায়নি!")
        return

    articles = []
    print("সংবাদ ও ছবি সংগ্রহের কাজ শুরু হচ্ছে...\n" + "=" * 50)

    for feed_info in RSS_FEEDS:
        print(f"\n[{feed_info['source']}] ফিড রিড করা হচ্ছে...")
        try:
            feed = feedparser.parse(feed_info["url"])
            selected_entries = feed.entries[:feed_info["limit"]]

            for entry in selected_entries:
                title = entry.get("title", "No Title").strip()
                link = entry.get("link", "#").strip()
                summary_raw = entry.get("summary", entry.get("description", ""))
                image_url = extract_image(entry)

                print(f"-> প্রসেস হচ্ছে: {title} (ছবি: {'হ্যাঁ' if image_url else 'না'})")
                ai_brief = generate_summary(api_key, title, summary_raw, feed_info["lang"])

                articles.append({
                    "source": feed_info["source"],
                    "title": title,
                    "link": link,
                    "image": image_url,
                    "summary": ai_brief
                })
        except Exception as err:
            print(f"ফিড পার্স এরর ({feed_info['source']}): {err}")

    # বাংলাদেশ সময় নির্ধারণ (UTC+6)
    bd_time = datetime.now(timezone(timedelta(hours=6)))
    last_updated_str = bd_time.strftime("%Y-%m-%d %I:%M %p")

    output_data = {
        "last_updated": last_updated_str,
        "articles": articles
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"মোট {len(articles)}টি খবর 'news.json' ফাইলে আপডেট সম্পন্ন!")

if __name__ == "__main__":
    main()
