# config.py
import os

# গিটহাব অ্যাকশনস থেকে কি খুঁজবে, না পেলে লোকাল কি ব্যবহার করবে
API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6LijyLZk6aMCXqCTphNnkXQ2raoNfW_EukKYY9oSTLwNA")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

RSS_FEEDS = [
    "https://prothomalo.com/stories.rss",
    "https://www.thedailystar.net/frontpage/rss.xml",
    "https://www.bbc.com/bengali/index.xml",
    "http://feeds.bbci.co.uk/news/world/rss.xml"
]