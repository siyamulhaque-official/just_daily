# news_fetcher.py
import feedparser
from config import RSS_FEEDS, USER_AGENT

print("খবর সংগ্রহ (Scraping) শুরু হচ্ছে...\n" + "="*50)

# daily_news.txt ফাইলে র-ডেটা (Raw Data) সেভ করা হচ্ছে
with open("daily_news.txt", "w", encoding="utf-8") as file:
    file.write("আজকের তাজা খবর (Raw Data)\n" + "="*50 + "\n")
    
    for url in RSS_FEEDS:
        try:
            # feedparser-এ User-Agent সেট করে রিকোয়েস্ট পাঠানো হচ্ছে
            feed = feedparser.parse(url, agent=USER_AGENT)
            
            source_name = feed.feed.get('title', 'Unknown Source / Blocked')
            print(f"ডেটা আনা হচ্ছে: {source_name}")
            
            file.write(f"\n--- সোর্স: {source_name} ---\n")
            
            # যদি ডেটা না আসে বা ব্লক থাকে
            if not feed.entries:
                file.write("কোনো ডেটা পাওয়া যায়নি! (হয়তো সার্ভারে ডেটা নেই বা ব্লক করেছে)\n")
            else:
                # প্রতিটি সোর্স থেকে লেটেস্ট ৩টি খবর ফাইলে লেখা হচ্ছে
                for i, entry in enumerate(feed.entries[:3]):
                    file.write(f"খবর {i+1}: {entry.title}\n")
                    file.write(f"তারিখ: {entry.get('published', 'No date')}\n")
                    file.write(f"লিংক: {entry.link}\n")
                    
            file.write("-" * 50 + "\n")
            
        except Exception as e:
            # যদি লিংক লোড হতে কোনো সমস্যা হয়
            print(f"[!] {url} থেকে ডেটা আনতে এরর: {e}")
            file.write(f"\n--- সোর্স: {url} ---\n")
            file.write(f"এরর: ডেটা ফেচ করা যায়নি। বিস্তারিত: {e}\n" + "-" * 50 + "\n")

print("\n" + "=" * 50)
print("খবরগুলো সফলভাবে 'daily_news.txt' ফাইলে সেভ হয়েছে!")