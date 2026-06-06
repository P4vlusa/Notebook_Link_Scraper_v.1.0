# -*- coding: utf-8 -*-
"""
Collect laptop product links from two LaptopWorld subcategories only:
- https://laptopworld.vn/laptop-van-phong.html
- https://laptopworld.vn/laptop-games-do-hoa.html
"""

import time
import argparse
import re
import os
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

BASE = "https://laptopworld.vn"
CATEGORIES = [
    "https://laptopworld.vn/laptop-van-phong.html",
    "https://laptopworld.vn/laptop-games-do-hoa.html",
]
DEALER = "LAPTOPWORLD"

PRODUCT_URL_PAT = re.compile(r"/(laptop|product|san-pham|sp|p-)", re.I)

PRICE_CLASS_PATTERNS = [
    re.compile(r"price", re.I),
    re.compile(r"gia", re.I),
    re.compile(r"product-price", re.I),
]
CURRENCY_TEXT_RE = re.compile(r"[0-9][\d.,\s]*[₫đvnd]|đ|₫", re.I)

PAGE_PAUSE = 0.8
LOAD_PAUSE = 1.0
USER_AGENT = "Mozilla/5.0 (compatible; laptopworld-collector/1.0)"


def headless_driver(headful=False):
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1200,2000")
    opts.add_argument(f"--user-agent={USER_AGENT}")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    return driver


def same_site(u: str) -> bool:
    try:
        return urlparse(u).netloc.endswith("laptopworld.vn")
    except Exception:
        return False


def looks_like_product_url(u: str) -> bool:
    if not same_site(u):
        return False
    return bool(PRODUCT_URL_PAT.search(u))


def fetch_soup(driver, url: str, pause: float = LOAD_PAUSE):
    try:
        driver.get(url)
    except WebDriverException:
        return None
    time.sleep(pause)
    return BeautifulSoup(driver.page_source, "html.parser")


def detect_total_pages(soup):
    if not soup:
        return 1
    nums = []
    for a in soup.select(".pagination a, .page a, nav a, .paging a"):
        txt = a.get_text(strip=True)
        if txt.isdigit():
            nums.append(int(txt))
        else:
            href = a.get("href") or ""
            m = re.search(r"[?&]page=(\d+)", href)
            if m:
                nums.append(int(m.group(1)))
    return max(nums) if nums else 1


def collect_links_from_category(driver, category_url, max_pages=200):
    links = set()
    first_soup = fetch_soup(driver, category_url)
    if not first_soup:
        return links

    total_pages = detect_total_pages(first_soup)
    total_pages = min(total_pages, max_pages)

    if total_pages == 1:
        consecutive_empty = 0
        pnum = 1
        while pnum <= max_pages and consecutive_empty < 2:
            page_url = f"{category_url}?page={pnum}"
            print(f"[INFO]   Loading page {pnum}: {page_url}")
            soup = fetch_soup(driver, page_url)
            if not soup:
                consecutive_empty += 1
                pnum += 1
                continue

            found = set()
            selectors = [".product a", ".product-item a", ".product-name a", ".item a", ".card a", "a"]
            for sel in selectors:
                for a in soup.select(sel):
                    href = a.get("href")
                    if not href:
                        continue
                    u = urljoin(BASE, href)
                    if looks_like_product_url(u):
                        found.add(u.split("#")[0])

            if found:
                consecutive_empty = 0
                links.update(found)
            else:
                consecutive_empty += 1
            pnum += 1
            time.sleep(PAGE_PAUSE)
    else:
        for pnum in range(1, total_pages + 1):
            page_url = f"{category_url}?page={pnum}"
            print(f"[INFO]   Loading page {pnum}/{total_pages}: {page_url}")
            soup = fetch_soup(driver, page_url)
            if not soup:
                continue

            selectors = [".product a", ".product-item a", ".product-name a", ".item a", ".card a", "a"]
            for sel in selectors:
                for a in soup.select(sel):
                    href = a.get("href")
                    if not href:
                        continue
                    u = urljoin(BASE, href)
                    if looks_like_product_url(u):
                        links.add(u.split("#")[0])
            time.sleep(PAGE_PAUSE)

    return links


def verify_price_in_soup(soup):
    if not soup:
        return False
    for tag in ["span", "div", "p", "b"]:
        for el in soup.find_all(tag):
            cls = el.get("class")
            if cls:
                cls_text = " ".join(cls)
                for pat in PRICE_CLASS_PATTERNS:
                    if pat.search(cls_text):
                        txt = el.get_text(" ", strip=True)
                        if txt and re.search(r"\d", txt):
                            return True
    if soup.find(string=re.compile(r"[0-9][\d.,\s]*[₫đvnd]|đ|₫", re.I)):
        return True
    return False


def extract_name_from_soup(soup):
    if not soup:
        return ""
    h1 = soup.find("h1")
    if h1:
        return " ".join(h1.get_text(" ", strip=True).split())
    og = soup.find("meta", {"property": "og:title"}) or soup.find("meta", {"name": "title"})
    if og and og.get("content"):
        return og["content"].strip()
    title = soup.find("title")
    if title:
        return " ".join(title.get_text(" ", strip=True).split())
    return ""


def extract_product_record(driver, url):
    try:
        driver.get(url)
    except WebDriverException:
        return None
    time.sleep(PAGE_PAUSE)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    if not verify_price_in_soup(soup):
        print(f"[DEBUG] No price found for {url}")
        return None

    name = extract_name_from_soup(soup)
    return {"name": name, "dealer": DEALER, "url": url}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    driver = headless_driver(headful=args.headful)
    out = []
    try:
        all_links = set()
        for cat in CATEGORIES:
            print(f"[INFO] Category: {cat}")
            found = collect_links_from_category(driver, cat)
            print(f"[INFO]   Collected {len(found)} links from category")
            all_links.update(found)

        print(f"[INFO] Total candidate links before dedupe: {len(all_links)}")
        links = sorted(all_links)

        for i, u in enumerate(links, 1):
            if args.no_verify:
                out.append({"name": "", "dealer": DEALER, "url": u})
            else:
                rec = extract_product_record(driver, u)
                if rec:
                    out.append(rec)
            if i % 20 == 0:
                print(f"[INFO] Processed {i}/{len(links)}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # --- EXPORT TO output/laptopworld.csv ---
    os.makedirs("output", exist_ok=True)
    csv_file = "output/laptopworld.csv"

    if out:
        df = pd.DataFrame(out)
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"[DONE] Wrote {len(out)} products to {csv_file}")
    else:
        print("[WARN] No products collected. CSV not created.")


if __name__ == "__main__":
    main()
