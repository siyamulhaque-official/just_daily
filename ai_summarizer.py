import json
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from time import mktime

FEEDS = {
    "Tech & Innovation": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml")
    ],
    "Science & Space": [
        ("Space.com", "https://www.space.com/feeds/all"),
        ("Phys.org", "https://phys.org/rss-feed/breaking/")
    ],
    "Business & Economy": [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex")
    ],
    "Global Affairs": [
        ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml")
    ],
    "Mind & Health": [
        ("Psyche", "https://psyche.co/feed.rss"),
        ("Medical News", "https://www.medicalnewstoday.com/rss")
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def generate_id(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def format_date(parsed_time):
    if parsed_time:
        try:
            dt = datetime.fromtimestamp(mktime(parsed_time))
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return ""
    return datetime.now(timezone.utc).strftime("%d %b %Y")

def extract_feed_image(entry):
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url', '')
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        return entry.media_thumbnail[0].get('url', '')
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        return entry.enclosures[0].get('href', '')
    return ""

def scrape_article(entry, link):
    image_url = extract_feed_image(entry)
    raw_html = ""

    if 'content' in entry and len(entry.content) > 0:
        raw_html = entry.content[0].value
    elif 'description' in entry:
        raw_html = entry.description

    try:
        response = requests.get(link, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            page_soup = BeautifulSoup(response.content, 'html.parser')

            # 1. Extract High-Res Cover Image (og:image / twitter:image)
            if not image_url:
                og_img = (
                    page_soup.find('meta', property='og:image') or
                    page_soup.find('meta', attrs={'name': 'twitter:image'}) or
                    page_soup.find('meta', property='og:image:url')
                )
                if og_img and og_img.get('content'):
                    image_url = og_img['content'].strip()

            # 2. Extract Full Article Body if feed content is short
            if len(BeautifulSoup(raw_html, 'html.parser').get_text(strip=True)) < 500:
                main_body = (
                    page_soup.find('div', class_='entry-content') or
                    page_soup.find('div', class_='wp-block-post-content') or
                    page_soup.find('div', class_='ArticleBody-articleBody') or
                    page_soup.find('article') or
                    page_soup.find('main') or
                    page_soup
                )
                raw_html = str(main_body)
    except Exception as e:
        print(f"Scraping warning for {link}: {e}")

    if not raw_html:
        return "", image_url

    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        # Fallback image from body if still empty
        if not image_url:
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src') and img_tag['src'].startswith('http'):
                image_url = img_tag['src']

        # Remove links but keep text
        for a in soup.find_all('a'):
            a.unwrap()

        # Remove non-content structural tags
        for tag in soup.find_all(['nav', 'footer', 'aside', 'script', 'style', 'button', 'form', 'figure', 'iframe', 'svg']):
            tag.decompose()

        # Remove junk/promotional blocks
        junk_keywords = ['share', 'social', 'newsletter', 'related', 'promo', 'jp-relatedposts', 'ad-slot', 'sidebar', 'caption']
        for tag in soup.find_all(True):
            if tag.has_attr('class'):
                class_str = ' '.join(tag['class']).lower() if isinstance(tag['class'], list) else str(tag['class']).lower()
                if any(k in class_str for k in junk_keywords):
                    tag.decompose()

        # Keep clean paragraphs and subheadings
        final_content = ""
        for el in soup.find_all(['p', 'h2', 'h3', 'h4']):
            text = el.get_text(strip=True)
            if len(text) > 35:
                final_content += f"<{el.name}>{text}</{el.name}>"
                if len(final_content) > 6500:
                    break

        return final_content, image_url
    except Exception as e:
        print(f"Content parsing error: {e}")
        return "", image_url

def main():
    news_data = []

    for category, sources in FEEDS.items():
        category_filled = False
        for source_name, feed_url in sources:
            if category_filled:
                break
            try:
                parsed_feed = feedparser.parse(feed_url)
                for entry in parsed_feed.entries[:6]:
                    try:
                        link = entry.get('link', '').strip()
                        title = entry.get('title', '').strip()
                        if not link or not title:
                            continue

                        pub_date = format_date(entry.get('published_parsed', entry.get('updated_parsed')))
                        print(f"[{category}] Checking: {title}")

                        full_html, image_url = scrape_article(entry, link)

                        if len(full_html) > 350:
                            news_data.append({
                                "id": generate_id(link),
                                "source": source_name,
                                "category": category,
                                "title": title,
                                "date": pub_date,
                                "link": link,
                                "image": image_url,
                                "full_text": full_html,
                                "summary": ""
                            })
                            category_filled = True
                            break
                    except Exception as entry_e:
                        print(f"Entry error: {entry_e}")
                        continue
            except Exception as feed_e:
                print(f"Feed error ({source_name}): {feed_e}")

    try:
        bst_time = datetime.now(timezone.utc) + timedelta(hours=6)
        output = {
            "last_updated": bst_time.strftime("%d %b %Y, %I:%M %p"),
            "articles": news_data
        }
        with open('news.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)
        print(f"Successfully updated news.json with {len(news_data)} articles.")
    except Exception as e:
        print(f"Error saving JSON: {e}")

if __name__ == "__main__":
    main()
