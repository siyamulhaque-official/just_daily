import os
import json
from datetime import datetime, timezone, timedelta
import feedparser

# Gemini SDK ইমপোর্ট হ্যান্ডলিং (নতুন এবং পুরাতন উভয় লাইব্রেরির জন্য নিরাপদ)
try:
    from google import genai
    USING_NEW_SDK = True
except ImportError:
    try:
        import google.generativeai as genai
        USING_NEW_SDK = False
    except ImportError:
        raise ImportError("কোনো Gemini SDK পাওয়া যায়নি! চালান: pip install google-genai")

# আরএসএস ফিড কনফিগারেশন (বাংলা ও ইংরেজি মিলিয়ে মোট ১২টি সংবাদ)
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
    """
    গিটহাব অ্যাকশনস এনভায়রনমেন্ট ভ্যারিয়েবল অথবা লোকাল config.py থেকে কি সংগ্রহ করে
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        try:
            import config
            key = getattr(config, "GEMINI_API_KEY", None)
        except ImportError:
            pass
    return key

def call_gemini(api_key, prompt):
    """
    Gemini API কল করার জেনেরিক ফাংশন
    """
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
    """
    ভাষা অনুযায়ী ৩-পয়েন্ট সামারি তৈরি করার প্রম্পট হ্যান্ডলার
    """
    if lang == "en":
        prompt = f"""
Summarize this news article for students into exactly 3 structured points in clean text:
**1. Core Concept:** (What happened in 1-2 clear sentences)
**2. Background:** (Why it happened / key context)
**3. Importance & Impact:** (Why readers or students should care)

Rules:
- Write strictly in simple, professional ENGLISH. Do NOT translate to Bengali.
- Keep the exact bold headings: **1. Core Concept:**, **2. Background:**, **3. Importance & Impact:**
- Do not write generic intros or pleasantries.

Title: {title}
Context: {context_text}
"""
    else:
        prompt = f"""
এই সংবাদটি একজন শিক্ষার্থীর সহজে বোঝার জন্য নিচের ৩টি পয়েন্টে সংক্ষেপ করো:
**১. মূল ঘটনা বা Core Concept:** (সংক্ষিপ্ত ১-২ বাক্যে)
**২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:** (কেন ঘটনাটি ঘটল)
**৩. এর প্রভাব বা গুরুত্ব:** (শিক্ষার্থীদের কেন এটি জানা জরুরি)

নিয়ম:
- সম্পূর্ণ উত্তরটি সহজ ও প্রাঞ্জল বাংলায় লিখবে। কোনো ভূমিকা বা উপসংহার লিখবে না।
- হুবহু এই বোল্ড হেডিংগুলো ব্যবহার করবে: **১. মূল ঘটনা বা Core Concept:**, **২. পেছনের কারণ বা ব্যাকগ্রাউন্ড:**, **৩. এর প্রভাব বা গুরুত্ব:**।

শিরোনাম: {title}
বিষয়বস্তু: {context_text}
"""

    try:
        return call_gemini(api_key, prompt)
    except Exception as e:
        print(f"এআই সামারি তৈরিতে এরর: {e}")
        return context_text[:180] + "..." if context_text else "বিস্তারিত তথ্য পাওয়া যায়নি।"

def main():
    api_key = get_api_key()
    if not api_key:
        print("ত্রুটি: কোনো GEMINI_API_KEY পাওয়া যায়নি! GitHub Secrets বা config.py চেক করুন।")
        return

    articles = []
    print("সংবাদ সংগ্রহ ও সামারাইজেশন প্রক্রিয়া শুরু হচ্ছে...\n" + "=" * 50)

    # ফিড থেকে সংবাদ রিড করা
    for feed_info in RSS_FEEDS:
        print(f"\n[{feed_info['source']}] থেকে সংবাদ রিড করা হচ্ছে...")
        try:
            feed = feedparser.parse(feed_info["url"])
            selected_entries = feed.entries[:feed_info["limit"]]

            for entry in selected_entries:
                title = entry.get("title", "No Title").strip()
                link = entry.get("link", "#").strip()
                summary_raw = entry.get("summary", entry.get("description", ""))

                print(f"-> প্রসেস করা হচ্ছে: {title}")
                ai_brief = generate_summary(api_key, title, summary_raw, feed_info["lang"])

                articles.append({
                    "source": feed_info["source"],
                    "title": title,
                    "link": link,
                    "summary": ai_brief
                })
        except Exception as err:
            print(f"ফিড পার্স করতে সমস্যা ({feed_info['source']}): {err}")

    # বাংলাদেশ সময় নির্ধারণ (UTC+6)
    bd_time = datetime.now(timezone(timedelta(hours=6)))
    last_updated_str = bd_time.strftime("%Y-%m-%d %I:%M %p")

    output_data = {
        "last_updated": last_updated_str,
        "articles": articles
    }

    # news.json ফাইলে সংরক্ষণ
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"সফলভাবে মোট {len(articles)}টি সংবাদ প্রসেস করে 'news.json' ফাইলে সেভ করা হয়েছে!")

if __name__ == "__main__":
    main()
