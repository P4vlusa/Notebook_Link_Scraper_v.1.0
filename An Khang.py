# -*- coding: utf-8 -*-
"""
AN KHANG laptop crawler
- Collects all laptop product URLs
- Extracts product name (H1)
- Saves to output/ankhang.csv
"""

import sys, time, argparse, re, os
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import pandas as pd

SEED_URL = "https://www.ankhang.vn/laptop.html"
DEALER   = "AN KHANG"
PRICE_TAG = ""
PRICE_CLASS = ""

UA = "Mozilla/5.0 (compatible; ankhang-collector/1.0)"
HEADERS = {"User-Agent": UA, "Accept-Language": "vi,en;q=0.8,*;q=0.6"}


def get(url, timeout=25):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def same_site(u: str) -> bool:
    try:
        return urlparse(u).netloc.endswith("ankhang.vn")
    except:
        return False


def looks_like_product_url(u: str) -> bool:
    if not same_site(u):
        return False
    path = urlparse(u).path.lower()
    if not path.endswith(".html"):
        return False
    if "laptop" not in path:
        return False
    bad = ("/tin-tuc", "/news", "/hoi-dap", "/blog", "/brand", "/collection")
    return not any(b in path for b in bad)


def collect_listing_links(seed: str, max_pages: int, delay: float):
    all_links = set()

    # Page 1 (no ?page=1)
    try:
        res = get(seed)
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(seed, a["href"].strip())
            if looks_like_product_url(href):
                all_links.add(href)
        time.sleep(delay)
    except Exception as e:
        print(f"[WARN] seed fetch failed: {e}")

    # Page 2..N
    for p in range(2, max_pages + 1):
        page_url = f"{seed}?page={p}"
        try:
            res = get(page_url)
        except:
            break

        soup = BeautifulSoup(res.text, "html.parser")
        before = len(all_links)

        for a in soup.find_all("a", href=True):
            href = urljoin(seed, a["href"].strip())
            if looks_like_product_url(href):
                all_links.add(href)

        added = len(all_links) - before
        print(f"[INFO] page {p}: +{added} items (total {len(all_links)})")

        if added == 0:
            break

        time.sleep(delay)

    return sorted(all_links)


def extract_name_from_product(url: str, delay: float):
    try:
        res = get(url)
    except Exception as e:
        print(f"[WARN] product fetch failed {url}: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    def text_of(el):
        return " ".join(el.get_text(" ", strip=True).split()) if el else None

    name = text_of(soup.find("h1"))
    if not name:
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            name = og["content"].strip()
    if not name:
        t = soup.find("title")
        name = text_of(t)

    time.sleep(delay * 0.5)
    if not name:
        return None

    return {
        "name": name,
        "dealer": DEALER,
        "url": url,
        "tag": PRICE_TAG,
        "class_name": PRICE_CLASS,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    print(f"[INFO] Crawling listing: {SEED_URL}")
    links = collect_listing_links(SEED_URL, args.max_pages, args.delay)
    print(f"[INFO] Found {len(links)} product links")

    out = []
    seen = set()

    for i, u in enumerate(links, 1):
        if u in seen:
            continue
        seen.add(u)

        rec = extract_name_from_product(u, args.delay)
        if rec:
            out.append(rec)

        if i % 25 == 0:
            print(f"[INFO] Checked {i}/{len(links)}")

    # SAVE TO output/ankhang.csv
    os.makedirs("output", exist_ok=True)
    df = pd.DataFrame(out)
    df.to_csv("output/ankhang.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(out)} products to output/ankhang.csv")


if __name__ == "__main__":
    main()
