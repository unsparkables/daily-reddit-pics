import datetime
import html
import os
import re
import requests
import xml.etree.ElementTree as ET

GITHUB_USER = "unsparkables"
REPO_NAME = "daily-reddit-pics"

SUBREDDITS = [
    {"name": "TheNightFeeling", "filename": "nightfeeling.xml", "desc": "Top night photograph from r/TheNightFeeling"},
    {"name": "LiminalSpace", "filename": "liminalspace.xml", "desc": "Top liminal space photograph from r/LiminalSpace"}
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp")
IMAGES_DIR = "images"

os.makedirs(IMAGES_DIR, exist_ok=True)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

def fetch_top_post_from_rss(subreddit):
    url = f"https://www.reddit.com/r/{subreddit}/top/.rss?sort=top&t=day&limit=5"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"Failed to fetch r/{subreddit}: HTTP {res.status_code}")
            return None

        root = ET.fromstring(res.content)
        entries = root.findall("atom:entry", ATOM_NS)
        
        for entry in entries:
            title = entry.find("atom:title", ATOM_NS).text or "Untitled"
            link = entry.find("atom:link", ATOM_NS).attrib.get("href", "")
            post_id = entry.find("atom:id", ATOM_NS).text.split("/")[-1]
            author = entry.find("atom:author/atom:name", ATOM_NS).text or "unknown"
            content = entry.find("atom:content", ATOM_NS).text or ""
            
            unescaped_content = html.unescape(content)
            
            img_matches = re.findall(r'href=[\'"](https://i\.redd\.it/[^\'"\s]+)[\'"]', unescaped_content)
            if not img_matches:
                img_matches = re.findall(r'(https://preview\.redd\.it/[^\'"\s<>]+)', unescaped_content)
            if not img_matches:
                img_matches = re.findall(r'src=[\'"](https://[^\'"\s]+\.(?:jpg|jpeg|png|webp)[^\'"\s]*)[\'"]', unescaped_content)
                
            if img_matches:
                img_url = img_matches[0].replace("&amp;", "&")
                return {
                    "title": title,
                    "link": link,
                    "id": post_id,
                    "author": author,
                    "img_url": img_url
                }

    except Exception as e:
        print(f"Error fetching r/{subreddit}: {e}")
    return None

def download_image(img_url, post_id, subreddit):
    ext = ".jpg"
    for e in VALID_EXTS:
        if e in img_url.lower():
            ext = e
            break

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    filename = f"{today_str}_{subreddit}_{post_id}{ext}"
    local_path = os.path.join(IMAGES_DIR, filename)

    if not os.path.exists(local_path):
        try:
            r = requests.get(img_url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                print(f"Successfully downloaded and saved: {filename}")
                return filename
            else:
                print(f"Image download returned status {r.status_code}")
        except Exception as e:
            print(f"Failed to download image {img_url}: {e}")
            return None
    return filename

def update_feed(filename, title, link, description, new_post, subreddit):
    existing_items = []
    try:
        tree = ET.parse(filename)
        channel = tree.getroot().find("channel")
        if channel is not None:
            existing_items = channel.findall("item")
    except Exception:
        pass

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "description").text = description

    if new_post:
        saved_filename = download_image(new_post["img_url"], new_post["id"], subreddit)
        if saved_filename:
            hosted_img_url = f"https://{GITHUB_USER}.github.io/{REPO_NAME}/{IMAGES_DIR}/{saved_filename}"
        else:
            hosted_img_url = new_post["img_url"]

        item = ET.Element("item")
        ET.SubElement(item, "title").text = new_post["title"]
        ET.SubElement(item, "link").text = new_post["link"]
        ET.SubElement(item, "guid").text = new_post["id"]
        ET.SubElement(item, "pubDate").text = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        desc_html = (
            f'<p><img src="{hosted_img_url}" alt="{new_post["title"]}" /></p>'
            f'<p><strong>r/{subreddit}</strong> | Posted by {new_post["author"]}</p>'
        )
        ET.SubElement(item, "description").text = desc_html
        channel.append(item)

    for old in existing_items[:29]:
        if new_post and old.find("guid") is not None and old.find("guid").text != new_post["id"]:
            channel.append(old)

    ET.ElementTree(rss).write(filename, encoding="utf-8", xml_declaration=True)

for sub in SUBREDDITS:
    winner = fetch_top_post_from_rss(sub["name"])
    if winner:
        print(f"Found top photo for r/{sub['name']}: {winner['title']}")
    update_feed(
        filename=sub["filename"],
        title=f"r/{sub['name']} - Daily Top Photo",
        link=f"https://www.reddit.com/r/{sub['name']}",
        description=sub["desc"],
        new_post=winner,
        subreddit=sub["name"]
    )
