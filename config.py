# config.py
import os

# লোকাল পরিবেশ বা ক্লাউড সিক্রেট থেকে কি নেওয়া হবে
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

RSS_FEEDS = [
    "https://prothomalo.com/stories.rss",
    "https://www.thedailystar.net/frontpage/rss.xml",
    "https://www.bbc.com/bengali/index.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml"
]
