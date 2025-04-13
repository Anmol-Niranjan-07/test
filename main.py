from fastapi import FastAPI, Query, HTTPException
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import re

app = FastAPI()

VALID_EXTENSIONS = ["png", "jpeg", "gif", "jpg", "webm"]

def build_base_url(tags: str, page: int) -> str:
    pid = (page - 1) * 42
    return f"https://realbooru.com/index.php?page=post&s=list&tags={tags}&pid={pid}"

async def fetch_html(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            raise HTTPException(status_code=resp.status, detail="Failed to fetch HTML content.")
        return await resp.text()

async def try_extensions(session, base_url_no_ext: str, extensions: list):
    for ext in extensions:
        full_url = f"{base_url_no_ext}.{ext}"
        async with session.head(full_url) as resp:
            if resp.status == 200:
                return full_url
    return None

async def fetch_images(session, pid_url):
    html = await fetch_html(session, pid_url)
    soup = BeautifulSoup(html, "html.parser")
    divs = soup.find_all("div", class_="col thumb")

    if not divs:
        raise HTTPException(status_code=404, detail="No results found.")

    image_data = []

    for div in divs:
        id_raw = div.get("id", "")
        post_id = id_raw[1:] if id_raw.startswith("s") else id_raw

        a_tag = div.find("a")
        if not a_tag:
            continue
        img_tag = a_tag.find("img")
        if not img_tag:
            continue

        img_src = img_tag.get("src")
        style = img_tag.get("style")
        title = img_tag.get("title", "")

        if not img_src or "thumbnail_" not in img_src:
            continue

        match = re.search(r"thumbnail_([a-fA-F0-9]+)\.jpg", img_src)
        if not match:
            continue

        hash_part = match.group(1)
        folder_parts = re.findall(r"/thumbnails/([^/]+)/([^/]+)/", img_src)
        if not folder_parts:
            continue
        folder1, folder2 = folder_parts[0]

        if style != "":
            file_base_url = f"https://video-cdn.realbooru.com/images/{folder1}/{folder2}/{hash_part}"
            is_video = True
        else:
            file_base_url = f"https://realbooru.com/images/{folder1}/{folder2}/{hash_part}"
            is_video = False

        image_data.append({
            "id": post_id,
            "title": title,
            "file_url": None,
            "base_url": file_base_url,
            "is_video": is_video
        })

    tasks = []
    for item in image_data:
        ext_order = ["webm"] if item["is_video"] else VALID_EXTENSIONS
        tasks.append(try_extensions(session, item["base_url"], ext_order))

    results = await asyncio.gather(*tasks)
    for idx, valid_url in enumerate(results):
        image_data[idx]["file_url"] = valid_url
        del image_data[idx]["base_url"]

    return image_data

@app.get("/search")
async def scrape(tags: str = Query(..., description="Search tags (required)"), page: int = Query(1, ge=1)):
    url = build_base_url(tags, page)
    async with aiohttp.ClientSession() as session:
        data = await fetch_images(session, url)
    return {"tags": tags, "page": page, "results": data}
