# ai_summarizer.py
import feedparser
import json
import time
import re
from datetime import datetime
from google import genai
from config import RSS_FEEDS, API_KEY 

client = genai.Client(api_key=API_KEY)

def clean_html(raw_html):
    # শিরোনাম থেকে অপ্রয়োজনীয় HTML ট্যাগ পরিষ্কার করার ফাংশন
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

print("ওয়েবের জন্য খবরের ডেটা প্রসেসিং শুরু হচ্ছে...\n" + "="*50)

all_news_data = {
    "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    "articles": []
}

for url in RSS_FEEDS:
    feed = feedparser.parse(url)
    source_name = feed.feed.get('title', 'Unknown Source')
    
    if not feed.entries:
        continue
        
    for entry in feed.entries[:2]:  # প্রতি সোর্স থেকে সেরা ২টি খবর
        raw_title = entry.title
        news_title = clean_html(raw_title)
        news_desc = clean_html(entry.get('description', 'কোনো বিবরণ নেই।'))
        
        prompt = f"""
        নিচে একটি খবরের শিরোনাম এবং বিবরণ দেওয়া হলো। একজন ছাত্রের (Student) জন্য উপযোগী করে এটিকে ৩টি পরিষ্কার পয়েন্টে বাংলায় ব্যাখ্যা কর:
        ১. মূল ঘটনা বা Core Concept
        ২. পেছনের কারণ বা ব্যাকগ্রাউন্ড
        ৩. এর প্রভাব বা গুরুত্ব

        খবরের শিরোনাম: {news_title}
        খবরের বিবরণ: {news_desc}
        """

        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
            )
            
            all_news_data["articles"].append({
                "source": source_name,
                "title": news_title,
                "link": entry.link,
                "summary": response.text.strip()
            })
            print(f"[✔] প্রসেস সফল: {news_title[:40]}...")
            
        except Exception as e:
            print(f"[!] স্কিপ করা হলো: {e}")
            
        time.sleep(2)

# news.json ফাইলে ডেটা রাইট করা
with open("news.json", "w", encoding="utf-8") as f:
    json.dump(all_news_data, f, ensure_ascii=False, indent=2)

print("\n" + "="*50)
print("সফলভাবে 'news.json' ফাইলে ওয়েব ডেটা তৈরি হয়েছে!")