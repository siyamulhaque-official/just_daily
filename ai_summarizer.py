#!/usr/bin/env python3
"""
Just Daily — AI News Summarizer
================================
Fetches headlines from a curated set of RSS feeds, scrapes the full body
text of each article, generates a professional AI summary via DeepSeek,
and writes everything to news.json for the static frontend to consume.

Run manually:
    DEEPSEEK_API_KEY=sk-xxxx python ai_summarizer.py

Run on a schedule via .github/workflows/update_news.yml
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
# NOTE: confirm this matches the exact model name active on your DeepSeek
# account/dashboard before relying on it in production.
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

MAX_ARTICLE_CHARS = 5000
MAX_ARTICLES_PER_SOURCE = 8
REQUEST_TIMEOUT = 15
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")

# "BST" in this project refers to Bangladesh Standard Time (UTC+6),
# not British Summer Time.
BST = timezone(timedelta(hours=6))

FEEDS = [
    {
        "name": "Al Jazeera",
        "category": "Global Affairs",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
    },
    {
        "name": "BBC World",
        "category": "Global Affairs",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "name": "TechCrunch",
        "category": "Tech & Innovation",
        "url": "https://techcrunch.com/feed/",
    },
    {
        "name": "Dev.to",
        "category": "Deep Reads",
        "url": "https://dev.to/feed",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Elements that never contain real article body copy.
STRIP_SELECTORS = [
    "script", "style", "nav", "footer", "header", "aside", "form",
    "iframe", "noscript", "svg", "button",
    ".advertisement", ".ad", ".ads", ".newsletter-signup",
    ".social-share", ".related-articles", ".comments",
]


def log(msg: str) -> None:
    stamp = datetime.now(BST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp} BST] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def fetch_full_article_text(url: str) -> str:
    """Download an article page and extract clean body text only."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log(f"  ! could not fetch article body ({exc})")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    for selector in STRIP_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    # Prefer a real <article> element; fall back to every <p> on the page.
    scope = soup.find("article") or soup
    paragraphs = scope.find_all("p")

    cleaned_paragraphs = []
    for p in paragraphs:
        para_text = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if para_text:
            cleaned_paragraphs.append(para_text)

    # Join with double newlines so the frontend can render real paragraphs.
    text = "\n\n".join(cleaned_paragraphs)

    return text[:MAX_ARTICLE_CHARS]


def extract_image(entry, article_url: str) -> str:
    """Best-effort attempt to find a representative image for the article."""
    media_content = entry.get("media_content") or []
    for m in media_content:
        if m.get("url"):
            return m["url"]

    media_thumbnail = entry.get("media_thumbnail") or []
    for m in media_thumbnail:
        if m.get("url"):
            return m["url"]

    for link in entry.get("links", []):
        if str(link.get("type", "")).startswith("image"):
            return link.get("href", "")

    # Fall back to the article's Open Graph image.
    try:
        resp = requests.get(article_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
    except requests.RequestException:
        pass

    return ""


# ---------------------------------------------------------------------------
# AI summarization
# ---------------------------------------------------------------------------

def generate_ai_summary(title: str, full_text: str) -> str:
    """Ask DeepSeek for a dynamic, professional English summary."""
    if not DEEPSEEK_API_KEY:
        log("  ! DEEPSEEK_API_KEY not set — skipping summary")
        return ""
    if not full_text:
        return ""

    system_prompt = (
        "You are a professional news editor writing for a premium, minimalist "
        "reading app. Write a dynamic, highly professional summary of the "
        "article in clear English prose (3 to 6 sentences). Naturally weave "
        "together the core event, relevant background, and its broader "
        "impact or significance. Do not use bullet points, labels, or a "
        "forced sentence count — let the summary's shape follow the story."
    )

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Title: {title}\n\nArticle:\n{full_text}"},
        ],
        "temperature": 0.4,
        "max_tokens": 400,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError) as exc:
        log(f"  ! DeepSeek summarization failed ({exc})")
        return ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_article_id(source: str, link: str) -> str:
    raw = f"{source}:{link}"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return slug[:80]


def load_existing(path: str) -> dict:
    """Load previously generated articles so we don't re-scrape/re-summarize them."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {a["id"]: a for a in data.get("articles", [])}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def main() -> None:
    existing = load_existing(OUTPUT_FILE)
    articles = []

    for feed in FEEDS:
        log(f"Fetching feed: {feed['name']}")
        parsed = feedparser.parse(feed["url"])

        if parsed.bozo and not parsed.entries:
            log(f"  ! could not parse {feed['name']} ({parsed.bozo_exception})")
            continue

        for entry in parsed.entries[:MAX_ARTICLES_PER_SOURCE]:
            link = entry.get("link", "")
            title = entry.get("title", "Untitled")
            if not link:
                continue

            article_id = build_article_id(feed["name"], link)

            if article_id in existing:
                articles.append(existing[article_id])
                continue

            log(f"  -> scraping: {title[:70]}")
            full_text = fetch_full_article_text(link)
            image = extract_image(entry, link)

            log("  -> summarizing with DeepSeek")
            summary = generate_ai_summary(title, full_text)

            articles.append({
                "id": article_id,
                "source": feed["name"],
                "category": feed["category"],
                "title": title,
                "link": link,
                "image": image,
                "full_text": full_text,
                "ai_summary": summary,
                "published_bst": datetime.now(BST).isoformat(),
            })

            time.sleep(1)  # be polite to source servers

    output = {
        "generated_at_bst": datetime.now(BST).isoformat(),
        "articles": articles,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"Done — wrote {len(articles)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
