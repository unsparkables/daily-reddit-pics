import datetime
import os
import requests
import xml.etree.ElementTree as ET

GITHUB_USER = "unsparkables"
REPO_NAME = "daily-reddit-pics"

SUBREDDITS = [
    {"name": "TheNightFeeling", "filename": "nightfeeling.xml", "desc": "Top night photograph from r/TheNightFeeling"},
    {"name": "LiminalSpace", "filename": "liminalspace.xml", "desc": "Top liminal space photograph from r/LiminalSpace"}
]

HEADERS = {"User-Agent": "daily-aesthetic-downloader/1.0"}
VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp")
IMAGES_DIR = "images"

os.makedirs(IMAGES_DIR, exist_ok=True)

def fetch_top_image(subreddit):
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit=10"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        posts = res.get("data", {}).get("children", [])
        
        for item in posts:
            data = item["data"]
            post_url = data.get("url", "")
            if any(post_url.lower().endswith(ext) for ext in VALID_EXTS) or "i.redd.it" in post_url:
                return data
        if posts:
            return posts[0]["data"]
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
            r = requests.get(img_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                print(f"Saved: {local_path}")
        except Exception as e:
            print(f"Failed to download image {img_url}: {e}")
            return None

    return filename

def update_feed(filename, title, link, description, new_post, subreddit):
    existing_items = []
    try:
        tree = ET.parse(filename)
        existing_items = tree.getroot().find("channel").findall("item")
    except Exception:
        pass

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "description").text = description

    if new_post:
        post_id = new_post["id"]
        remote_img_url = new_post.get("url", "")
        saved_filename = download_image(remote_img_url, post_id, subreddit)

        if saved_filename:
            hosted_img_url = f"https://{GITHUB_USER}.github.io/{REPO_NAME}/{IMAGES_DIR}/{saved_filename}"
        else:
            hosted_img_url = remote_img_url

        item = ET.Element("item")
        ET.SubElement(item, "title").text = new_post["title"]
        ET.SubElement(item, "link").text = f"https://reddit.com{new_post['permalink']}"
        ET.SubElement(item, "guid").text = post_id
        ET.SubElement(item, "pubDate").text = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        desc_html = (
            f'<p><img src="{hosted_img_url}" alt="{new_post["title"]}" /></p>'
            f'<p><strong>r/{subreddit}</strong> | Score: {new_post["score"]} | u/{new_post["author"]}</p>'
        )
        ET.SubElement(item, "description").text = desc_html
        channel.append(item)

    for old in existing_items[:29]:
        if new_post and old.find("guid").text != new_post["id"]:
            channel.append(old)

    ET.ElementTree(rss).write(filename, encoding="utf-8", xml_declaration=True)

for sub in SUBREDDITS:
    winner = fetch_top_image(sub["name"])
    update_feed(
        filename=sub["filename"],
        title=f"r/{sub['name']} - Daily Top Photo",
        link=f"https://www.reddit.com/r/{sub['name']}",
        description=sub["desc"],
        new_post=winner,
        subreddit=sub["name"]
    )
