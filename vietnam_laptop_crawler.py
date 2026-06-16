#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vietnam Laptop Crawler v2.2
============================
Thu thập tên sản phẩm + link từ 13 website bán laptop Việt Nam.

Websites:
  1.  gearvn.com          - Shopify sitemap + product.json API
  2.  xgear.net           - Shopify JSON API multi-page
  3.  tinhocngoisao.com   - Shopify JSON API multi-page
  4.  hangchinhhieu.vn    - Shopify JSON API multi-page
  5.  laptopnew.vn        - Shopify collection API
  6.  memoryzone.com.vn   - Shopify JSON API / CSS selectors
  7.  cellphones.com.vn   - Playwright + click "Xem thêm"
  8.  hoanghamobile.com   - BeautifulSoup category pages
  9.  laptopworld.vn      - BeautifulSoup + .hover_name (no H1 fetch)
  10. laptop88.vn         - BeautifulSoup + /new-100- pattern
  11. anphatpc.com.vn     - Sitemap XML + threading
  12. hacom.vn            - Playwright (JS-rendered)
  13. phucanh.vn          - BeautifulSoup brand pages (cần IP VN)

Cài đặt:
  pip install requests beautifulsoup4 lxml playwright
  python -m playwright install chromium

Sử dụng:
  python vietnam_laptop_crawler.py
  python vietnam_laptop_crawler.py --sites gearvn laptopworld hacom
  python vietnam_laptop_crawler.py --output my_laptops.csv --delay 1.5
  python vietnam_laptop_crawler.py --no-playwright
"""

import argparse
import asyncio
import csv
import os
import random
import re
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT = "vietnam_laptops.csv"
DEFAULT_DELAY = 0.5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

DELAY = DEFAULT_DELAY


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def get_json_headers():
    return {**get_headers(), "Accept": "application/json, text/plain, */*"}


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def dedup(products):
    seen, result = set(), []
    for p in products:
        name = clean(p.get("name", ""))
        url = p.get("url", "").strip()
        if url and url not in seen and len(name) > 4:
            seen.add(url)
            result.append({"name": name, "url": url})
    return result


def get_soup(url, session=None, timeout=25, retries=3):
    s = session or requests.Session()
    for attempt in range(retries):
        try:
            r = s.get(url, headers=get_headers(), timeout=timeout, verify=False)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            elif r.status_code in (429, 503):
                wait = (attempt + 1) * 5
                print(f"    Rate limited ({r.status_code}), waiting {wait}s...", flush=True)
                time.sleep(wait)
            elif r.status_code == 403:
                return None
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(2)
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
    return None


def extract_h1(soup):
    if not soup:
        return ""
    h1 = soup.find("h1")
    if h1:
        return clean(h1.get_text())
    og = soup.find("meta", {"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()
    t = soup.find("title")
    return clean(t.get_text()) if t else ""


def save_csv(products, filename=DEFAULT_OUTPUT):
    """Save products to CSV in same directory as this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(filename) and not os.path.dirname(filename):
        filename = os.path.join(script_dir, filename)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Tên sản phẩm", "Link sản phẩm"])
        for p in products:
            writer.writerow([p["name"], p["url"]])
    print(f"  ✓ Saved {len(products)} products → {filename}")


def log(site, msg):
    print(f"  [{site}] {msg}", flush=True)


def sleep(factor=1.0):
    t = DELAY * factor * (0.8 + random.random() * 0.4)
    time.sleep(t)


# ─────────────────────────────────────────────────────────────────────────────
# SHOPIFY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _shopify_json_api(base_url, collection_path, label, max_pages=200):
    """Use Shopify /products.json API - auto-detects page size."""
    session = requests.Session()
    products = []
    seen = set()

    # First request to detect actual page size
    test_url = f"{base_url}/collections/{collection_path}/products.json?limit=250&page=1"
    try:
        r = session.get(test_url, headers=get_json_headers(), timeout=15, verify=False)
        if r.status_code != 200:
            return []
        first_items = r.json().get("products", [])
        if not first_items:
            return []
        actual_limit = len(first_items)
        log(label, f"JSON p1 (limit={actual_limit}): {actual_limit} (total {actual_limit})")
        for item in first_items:
            title = item.get("title", "").strip()
            handle = item.get("handle", "")
            prod_url = f"{base_url}/products/{handle}"
            if title and prod_url not in seen:
                seen.add(prod_url)
                products.append({"name": title, "url": prod_url})
    except Exception as e:
        log(label, f"JSON API error p1: {e}")
        return []

    page = 2
    while page <= max_pages:
        url = f"{base_url}/collections/{collection_path}/products.json?limit={actual_limit}&page={page}"
        try:
            r = session.get(url, headers=get_json_headers(), timeout=15, verify=False)
            if r.status_code != 200:
                break
            items = r.json().get("products", [])
            if not items:
                break
            for item in items:
                title = item.get("title", "").strip()
                handle = item.get("handle", "")
                prod_url = f"{base_url}/products/{handle}"
                if title and prod_url not in seen:
                    seen.add(prod_url)
                    products.append({"name": title, "url": prod_url})
            log(label, f"JSON p{page}: {len(items)} (total {len(products)})")
            if len(items) < actual_limit:
                break
            page += 1
            sleep(0.2)
        except Exception as e:
            log(label, f"JSON API error p{page}: {e}")
            break

    return dedup(products)


def _shopify_paginated_h1(base_url, site_base, label, max_pages=20):
    """Collect /products/ links then fetch H1 in parallel."""
    session = requests.Session()
    links = set()

    for page in range(1, max_pages + 1):
        url = f"{base_url}?page={page}"
        soup = get_soup(url, session)
        if not soup:
            break
        found = set()
        for sel in [".product-card a", ".product-item a", ".product-item__info a", "a"]:
            for a in soup.select(sel):
                href = a.get("href")
                if href:
                    u = urljoin(site_base, href).split("#")[0]
                    if "/products/" in u:
                        found.add(u)
        if not found:
            break
        links.update(found)
        log(label, f"page {page}: +{len(found)} (total {len(links)})")
        sleep(0.3)

    products = []
    url_list = sorted(links)
    log(label, f"Fetching names for {len(url_list)} products...")

    def fetch_one(url):
        soup = get_soup(url, timeout=15)
        name = extract_h1(soup)
        return {"name": name, "url": url} if name else None

    for i in range(0, len(url_list), 10):
        batch = url_list[i:i+10]
        with ThreadPoolExecutor(max_workers=5) as ex:
            for result in as_completed([ex.submit(fetch_one, u) for u in batch]):
                r = result.result()
                if r:
                    products.append(r)
        if i % 50 == 0 and i > 0:
            log(label, f"  fetched {i}/{len(url_list)}: {len(products)} products")
        time.sleep(0.2)

    return dedup(products)


# ─────────────────────────────────────────────────────────────────────────────
# 1. GEARVN
# ─────────────────────────────────────────────────────────────────────────────

def crawl_gearvn():
    print("\n[1/13] GEARVN ...", flush=True)
    session = requests.Session()
    LAPTOP_KW = ["laptop", "may-tinh-xach-tay", "macbook", "notebook"]

    laptop_urls = []
    for i in range(1, 6):
        try:
            r = session.get(
                f"https://gearvn.com/sitemap_products_{i}.xml",
                headers=get_json_headers(), timeout=20, verify=False
            )
            if r.status_code != 200:
                break
            urls = re.findall(r"<loc>(https://gearvn\.com/products/[^<]+)</loc>", r.text)
            canonical = [u for u in urls if "?" not in u]
            laptop = [u for u in canonical if any(kw in u.lower() for kw in LAPTOP_KW)]
            laptop_urls.extend(laptop)
            log("GEARVN", f"sitemap_{i}: {len(canonical)} total, {len(laptop)} laptop")
            if len(canonical) < 500:
                break
            sleep()
        except Exception as e:
            log("GEARVN", f"sitemap_{i} error: {e}")
            break

    log("GEARVN", f"Total laptop URLs: {len(laptop_urls)}")

    products = []
    seen = set()
    for i, url in enumerate(laptop_urls):
        handle = url.split("/products/")[-1]
        try:
            r = session.get(
                f"https://gearvn.com/products/{handle}.json",
                headers=get_json_headers(), timeout=10, verify=False
            )
            if r.status_code == 200:
                prod = r.json().get("product", {})
                title = prod.get("title", "").strip()
                if title and url not in seen:
                    seen.add(url)
                    products.append({"name": title, "url": url})
            time.sleep(0.08)
        except Exception:
            pass
        if (i + 1) % 100 == 0:
            log("GEARVN", f"Fetched {i+1}/{len(laptop_urls)}: {len(products)} products")

    products = dedup(products)
    log("GEARVN", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 2. XGEAR
# ─────────────────────────────────────────────────────────────────────────────

def crawl_xgear():
    print("\n[2/13] XGEAR ...", flush=True)
    p = _shopify_json_api("https://xgear.net", "laptop", "XGEAR")
    if len(p) < 10:
        p = _shopify_paginated_h1("https://xgear.net/collections/laptop", "https://xgear.net", "XGEAR")
    log("XGEAR", f"→ {len(p)} sản phẩm")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# 3. TINHOCNGOISAO
# ─────────────────────────────────────────────────────────────────────────────

def crawl_tinhocngoisao():
    print("\n[3/13] TINHOCNGOISAO ...", flush=True)
    p = _shopify_json_api("https://tinhocngoisao.com", "laptop", "TINHOCNGOISAO")
    if len(p) < 10:
        p = _shopify_paginated_h1(
            "https://tinhocngoisao.com/collections/laptop",
            "https://tinhocngoisao.com", "TINHOCNGOISAO"
        )
    log("TINHOCNGOISAO", f"→ {len(p)} sản phẩm")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# 4. HANGCHINHHIEU
# ─────────────────────────────────────────────────────────────────────────────

def crawl_hangchinhhieu():
    print("\n[4/13] HANGCHINHHIEU ...", flush=True)
    p1 = _shopify_json_api("https://hangchinhhieu.vn", "laptop", "HCH-laptop")
    p2 = _shopify_json_api("https://hangchinhhieu.vn", "laptop-gaming-do-hoa-studio", "HCH-gaming")
    products = dedup(p1 + p2)
    products = [p for p in products if any(kw in p["name"].lower()
                for kw in ["laptop", "macbook", "surface", "notebook"])]
    log("HANGCHINHHIEU", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 5. LAPTOPNEW
# ─────────────────────────────────────────────────────────────────────────────

def crawl_laptopnew():
    print("\n[5/13] LAPTOPNEW ...", flush=True)
    BASE = "https://laptopnew.vn"
    session = requests.Session()
    products = []
    seen = set()

    for col in ["laptop-gaming", "laptop-van-phong"]:
        page = 1
        while True:
            url = f"{BASE}/collections/{col}/products.json?limit=250&page={page}"
            try:
                r = session.get(url, headers=get_json_headers(), timeout=15, verify=False)
                if r.status_code != 200:
                    break
                items = r.json().get("products", [])
                if not items:
                    break
                for item in items:
                    title = item.get("name", "").strip()
                    prod_url = urljoin(BASE, item.get("url", ""))
                    if title and prod_url not in seen:
                        seen.add(prod_url)
                        products.append({"name": title, "url": prod_url})
                log("LAPTOPNEW", f"{col} page {page}: {len(items)}")
                if len(items) < 250:
                    break
                page += 1
                sleep(0.3)
            except Exception as e:
                log("LAPTOPNEW", f"error: {e}")
                break

    products = dedup(products)
    log("LAPTOPNEW", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 6. MEMORYZONE
# ─────────────────────────────────────────────────────────────────────────────

def crawl_memoryzone():
    print("\n[6/13] MEMORYZONE ...", flush=True)
    p = _shopify_json_api("https://memoryzone.com.vn", "laptop", "MEMORYZONE")
    if len(p) < 10:
        CATS = [
            "https://memoryzone.com.vn/laptop",
            "https://memoryzone.com.vn/laptop-do-hoa",
        ]
        SELECTORS = [
            "h3.product-name a", ".product-name a",
            ".proloop-title a", ".product-card .product-name a",
            ".product-thumbnail a[title]", ".product-info a[title]",
        ]
        SKIP = ("/blogs/", "/tin-tuc", "/khuyen-mai", "/pages/", "#")
        session = requests.Session()
        products = []
        seen = set()
        for cat in CATS:
            cat_name = cat.split("/")[-1]
            for page in range(1, 50):
                url = cat if page == 1 else f"{cat}?page={page}"
                soup = get_soup(url, session)
                if not soup:
                    break
                found = 0
                for sel in SELECTORS:
                    for a in soup.select(sel):
                        href = (a.get("href") or "").strip()
                        if not href or any(f in href for f in SKIP):
                            continue
                        href = urljoin(url, href)
                        name = (a.get("aria-label") or a.get("title") or clean(a.get_text()))
                        if href not in seen and name and len(name) > 5:
                            seen.add(href)
                            products.append({"name": name, "url": href})
                            found += 1
                log("MEMORYZONE", f"{cat_name} page {page}: {found}")
                if page > 1 and found == 0:
                    break
                sleep()
        p = dedup(products)
    log("MEMORYZONE", f"→ {len(p)} sản phẩm")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# 7. CELLPHONES — Playwright + click "Xem thêm"
# ─────────────────────────────────────────────────────────────────────────────

async def _crawl_cellphones_async():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  [CELLPHONES] Playwright not installed.", flush=True)
        return []

    CATS = [
        "https://cellphones.com.vn/laptop.html",
        "https://cellphones.com.vn/laptop/van-phong.html",
        "https://cellphones.com.vn/laptop/gaming.html",
        "https://cellphones.com.vn/laptop/do-hoa.html",
        "https://cellphones.com.vn/laptop/sinh-vien.html",
        "https://cellphones.com.vn/laptop/mong-nhe.html",
        "https://cellphones.com.vn/laptop/asus.html",
        "https://cellphones.com.vn/laptop/hp.html",
        "https://cellphones.com.vn/laptop/lenovo.html",
        "https://cellphones.com.vn/laptop/acer.html",
        "https://cellphones.com.vn/laptop/dell.html",
        "https://cellphones.com.vn/laptop/msi.html",
        "https://cellphones.com.vn/laptop/gigabyte.html",
        "https://cellphones.com.vn/laptop/lg.html",
    ]

    def extract_products(html):
        soup = BeautifulSoup(html, "lxml")
        products = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = clean(a.get_text())
            if ("laptop-" in href and href.endswith(".html") and
                    "cellphones.com.vn" in href and len(text) > 5):
                name = re.split(r"Trả góp|[\d]{2,}\.[\d]{3}", text)[0].strip()
                name = clean(name)
                if len(name) > 5:
                    products.append({"name": name, "url": href})
        return products

    global_seen = set()
    all_rows = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--ignore-certificate-errors",
                  "--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "vi-VN,vi;q=0.9"}
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await ctx.new_page()

        for cat_url in CATS:
            cat_name = cat_url.split("/")[-1]
            try:
                await page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
            except Exception as e:
                log("CELLPHONES", f"{cat_name} error: {e}")
                continue

            cat_seen = set()
            click_count = 0

            while click_count < 50:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                clicked = False
                for sel in ["a.btn-show-more.button__show-more-product",
                             "a.button__show-more-product", ".btn-show-more"]:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=800):
                            await btn.scroll_into_view_if_needed()
                            await btn.click()
                            await asyncio.sleep(2.5)
                            clicked = True
                            click_count += 1
                            break
                    except Exception:
                        pass

                html = await page.content()
                current = extract_products(html)
                new_in_cat = sum(1 for p in current if p["url"] not in cat_seen)
                for p in current:
                    cat_seen.add(p["url"])
                    if p["url"] not in global_seen:
                        global_seen.add(p["url"])
                        all_rows.append(p)

                log("CELLPHONES", f"{cat_name} click {click_count}: {new_in_cat} new (total {len(all_rows)})")
                if not clicked or new_in_cat == 0:
                    break

        await browser.close()

    return dedup(all_rows)


def crawl_cellphones():
    print("\n[7/13] CELLPHONES ...", flush=True)
    try:
        products = asyncio.run(_crawl_cellphones_async())
    except Exception as e:
        log("CELLPHONES", f"Error: {e}")
        products = []
    log("CELLPHONES", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 8. HOANGHAMOBILE
# ─────────────────────────────────────────────────────────────────────────────

def crawl_hoanghamobile():
    print("\n[8/13] HOANGHAMOBILE ...", flush=True)
    BASE = "https://hoanghamobile.com"
    CATS = [
        "https://hoanghamobile.com/laptop",
        "https://hoanghamobile.com/laptop/van-phong-sinh-vien",
        "https://hoanghamobile.com/laptop/phan-loai-san-pham/do-hoa-ki-thuat",
        "https://hoanghamobile.com/laptop/phan-loai-san-pham/laptop-gaming",
        "https://hoanghamobile.com/laptop/macbook",
        "https://hoanghamobile.com/laptop/asus",
        "https://hoanghamobile.com/laptop/dell",
        "https://hoanghamobile.com/laptop/hp",
        "https://hoanghamobile.com/laptop/lenovo",
        "https://hoanghamobile.com/laptop/acer",
        "https://hoanghamobile.com/laptop/msi",
        "https://hoanghamobile.com/laptop/lg",
    ]
    session = requests.Session()
    products = []
    seen = set()

    for cat in CATS:
        cat_name = cat.split("/laptop/")[-1] if "/laptop/" in cat else "laptop"
        page = 1
        while page <= 50:
            url = cat if page == 1 else f"{cat}?p={page}"
            soup = get_soup(url, session)
            if not soup:
                break
            found = 0
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                title = a.get("title", "")
                text = clean(a.get_text())
                name = title if title else text
                full_url = urljoin(BASE, href) if not href.startswith("http") else href
                depth = full_url.count("/")
                if (full_url not in seen and
                        "hoanghamobile.com/laptop/" in full_url and
                        len(name) > 8 and len(name) < 200 and
                        depth == 4 and
                        not any(kw in full_url for kw in [
                            "/van-phong-sinh-vien", "/do-hoa-ki-thuat",
                            "/laptop-gaming", "/phan-loai-san-pham",
                            "/laptop-lg-gram", "/laptop-ai",
                        ])):
                    seen.add(full_url)
                    products.append({"name": name, "url": full_url})
                    found += 1
            log("HOANGHAMOBILE", f"{cat_name} p={page}: {found} (total {len(products)})")
            next_links = soup.find_all("a", href=re.compile(r"[?&]p=\d+"))
            next_pages = set()
            for nl in next_links:
                m = re.search(r"[?&]p=(\d+)", nl.get("href", ""))
                if m:
                    next_pages.add(int(m.group(1)))
            if page + 1 not in next_pages:
                break
            page += 1
            sleep(0.5)

    products = dedup(products)
    log("HOANGHAMOBILE", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 9. LAPTOPWORLD — .hover_name (no H1 fetch needed)
# ─────────────────────────────────────────────────────────────────────────────

def crawl_laptopworld():
    print("\n[9/13] LAPTOPWORLD ...", flush=True)
    BASE = "https://laptopworld.vn"
    CATS = [
        "https://laptopworld.vn/laptop-van-phong.html",
        "https://laptopworld.vn/laptop-games-do-hoa.html",
    ]
    session = requests.Session()
    products = []
    seen = set()

    for cat in CATS:
        cat_name = cat.split("/")[-1]
        for page in range(1, 100):
            url = cat if page == 1 else f"{cat}?page={page}"
            soup = get_soup(url, session)
            if not soup:
                break
            p_items = soup.select(".p-item")
            if not p_items:
                break
            found = 0
            for item in p_items:
                a = item.select_one(".p-name a") or item.find("a", href=True)
                if not a:
                    continue
                href = a.get("href", "")
                hover = item.select_one(".hover_name")
                name = clean(hover.get_text()) if hover else (a.get("title", "") or clean(a.get_text()))
                if href and name and len(name) > 5:
                    full_url = urljoin(BASE, href)
                    if full_url not in seen:
                        seen.add(full_url)
                        products.append({"name": name, "url": full_url})
                        found += 1
            log("LAPTOPWORLD", f"{cat_name} page {page}: {found} (total {len(products)})")
            if found == 0:
                break
            sleep(0.3)

    products = dedup(products)
    log("LAPTOPWORLD", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 10. LAPTOP88 — /new-100- URL pattern
# ─────────────────────────────────────────────────────────────────────────────

def crawl_laptop88():
    print("\n[10/13] LAPTOP88 ...", flush=True)
    BASE_URL = "https://laptop88.vn/may-tinh-xach-tay.html"
    DOMAIN = "https://laptop88.vn"
    PRODUCT_RE = re.compile(r"/new-100-[a-z0-9\-]+", re.IGNORECASE)
    session = requests.Session()
    products = []
    seen = set()
    page = 1

    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
        soup = get_soup(url, session)
        if not soup:
            break
        found = 0
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if PRODUCT_RE.search(href):
                prod_url = urljoin(DOMAIN, href)
                if prod_url in seen:
                    continue
                name = clean(a.get_text())
                if not name or len(name) < 5:
                    for ancestor in [a.parent, a.parent.parent if a.parent else None]:
                        if ancestor:
                            h = ancestor.find(["h2", "h3", "h4"])
                            if h:
                                name = clean(h.get_text())
                                break
                if name and len(name) > 5:
                    seen.add(prod_url)
                    products.append({"name": name, "url": prod_url})
                    found += 1
        if found == 0:
            break
        log("LAPTOP88", f"page {page}: {found} (total {len(products)})")
        page += 1
        sleep(0.5)

    products = dedup(products)
    log("LAPTOP88", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 11. ANPHATPC — Sitemap XML + threading
# ─────────────────────────────────────────────────────────────────────────────

def crawl_anphatpc(max_urls=3000):
    print("\n[11/13] ANPHATPC ...", flush=True)
    session = requests.Session()

    r = session.get(
        "https://www.anphatpc.com.vn/sitemap_product.xml",
        headers=get_headers(), timeout=30, verify=False
    )
    all_urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    EXCLUDE = ["bao-hanh", "bao-ve", "gia-han", "goi-", "phu-kien",
               "linh-kien", "man-hinh", "chuot", "ban-phim", "tai-nghe", "tui", "balo"]
    laptop_urls = [
        u for u in all_urls
        if any(kw in u.lower() for kw in ["laptop", "may-tinh-xach-tay", "macbook"])
        and not any(ex in u.lower() for ex in EXCLUDE)
    ]
    laptop_urls = laptop_urls[:max_urls]
    log("ANPHATPC", f"Total laptop URLs: {len(laptop_urls)}")

    def fetch_one(url):
        soup = get_soup(url, timeout=10)
        name = extract_h1(soup)
        return {"name": name, "url": url} if name else None

    products = []
    for i in range(0, len(laptop_urls), 20):
        batch = laptop_urls[i:i+20]
        with ThreadPoolExecutor(max_workers=8) as ex:
            for result in as_completed([ex.submit(fetch_one, u) for u in batch]):
                r = result.result()
                if r:
                    products.append(r)
        if i % 200 == 0:
            log("ANPHATPC", f"{i}/{len(laptop_urls)}: {len(products)} products")
        time.sleep(0.1)

    products = dedup(products)
    log("ANPHATPC", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 12. HACOM — Playwright (JS-rendered) + fallback
# ─────────────────────────────────────────────────────────────────────────────

async def _crawl_hacom_async():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    BASE = "https://hacom.vn"
    CATS = ["https://hacom.vn/laptop", "https://hacom.vn/laptop-gaming-do-hoa"]
    PRODUCT_RE = re.compile(r"hacom\.vn/laptop-[a-z0-9]", re.IGNORECASE)
    EXCLUDE = ["laptop-gaming-do-hoa", "laptop-tablet", "khuyen-mai", "tin-tuc",
               "chinh-sach", "huong-dan", "tra-don", "showroom", "gioi-thieu",
               "tuyen-dung", "buildpc", "lien-he", "laptop-do-hoa$"]

    products = []
    seen = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--ignore-certificate-errors"]
        )
        ctx = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "vi-VN,vi;q=0.9"}
        )
        page = await ctx.new_page()

        for cat_url in CATS:
            cat_name = cat_url.split("/")[-1]
            pg = 1
            while pg <= 50:
                url = cat_url if pg == 1 else f"{cat_url}?page={pg}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    for _ in range(3):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1)
                except Exception as e:
                    log("HACOM", f"{cat_name} p{pg} error: {e}")
                    break

                html = await page.content()
                soup = BeautifulSoup(html, "lxml")
                found = 0
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    title = a.get("title", "")
                    text = clean(a.get_text())
                    name = title if title else text
                    full_url = urljoin(BASE, href) if not href.startswith("http") else href
                    if (PRODUCT_RE.search(full_url) and
                            full_url not in seen and
                            len(name) > 10 and len(name) < 250 and
                            not any(ex in full_url for ex in EXCLUDE)):
                        seen.add(full_url)
                        products.append({"name": name, "url": full_url})
                        found += 1
                log("HACOM", f"{cat_name} p{pg}: {found} (total {len(products)})")
                if found == 0:
                    break
                pg += 1

        await browser.close()

    return dedup(products)


def _crawl_hacom_fallback():
    BASE = "https://hacom.vn"
    BRAND_CATS = [
        "https://hacom.vn/laptop-asus-vivobook", "https://hacom.vn/laptop-asus-zenbook",
        "https://hacom.vn/laptop-asus-expertbook", "https://hacom.vn/laptop-asus-rog",
        "https://hacom.vn/laptop-asus-tuf", "https://hacom.vn/laptop-dell-inspiron",
        "https://hacom.vn/laptop-dell-latitude", "https://hacom.vn/laptop-dell-xps",
        "https://hacom.vn/laptop-dell-vostro", "https://hacom.vn/laptop-acer-aspire",
        "https://hacom.vn/laptop-acer-gaming", "https://hacom.vn/laptop-acer-swift",
        "https://hacom.vn/laptop-hp-pavilion", "https://hacom.vn/laptop-hp-victus",
        "https://hacom.vn/laptop-hp-elitebook", "https://hacom.vn/laptop-lenovo-ideapad",
        "https://hacom.vn/laptop-lenovo-thinkpad", "https://hacom.vn/laptop-lenovo-legion",
        "https://hacom.vn/laptop-lenovo-loq", "https://hacom.vn/laptop-msi-gaming",
        "https://hacom.vn/laptop-msi-modern", "https://hacom.vn/laptop-apple-macbook-air",
        "https://hacom.vn/laptop-apple-macbook-pro", "https://hacom.vn/laptop-gigabyte-gaming",
        "https://hacom.vn/laptop-lg-gram",
    ]
    PRODUCT_RE = re.compile(r"hacom\.vn/laptop-[a-z0-9]+-[a-z0-9]+-[a-z0-9]", re.IGNORECASE)
    session = requests.Session()
    products = []
    seen = set()

    for cat_url in BRAND_CATS:
        cat_name = cat_url.split("/")[-1]
        for pg in range(1, 20):
            url = cat_url if pg == 1 else f"{cat_url}?page={pg}"
            soup = get_soup(url, session)
            if not soup:
                break
            found = 0
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                title = a.get("title", "")
                text = clean(a.get_text())
                name = title if title else text
                full_url = urljoin(BASE, href) if not href.startswith("http") else href
                if (PRODUCT_RE.search(full_url) and
                        full_url not in seen and
                        len(name) > 10 and len(name) < 250):
                    seen.add(full_url)
                    products.append({"name": name, "url": full_url})
                    found += 1
            log("HACOM", f"{cat_name} p{pg}: {found} (total {len(products)})")
            if found == 0:
                break
            sleep(0.5)

    return dedup(products)


def crawl_hacom():
    print("\n[12/13] HACOM ...", flush=True)
    try:
        products = asyncio.run(_crawl_hacom_async())
        if products is None:
            log("HACOM", "Playwright not available, using fallback...")
            products = _crawl_hacom_fallback()
    except Exception as e:
        log("HACOM", f"Playwright error: {e}, using fallback...")
        products = _crawl_hacom_fallback()
    log("HACOM", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# 13. PHUCANH — BeautifulSoup brand pages (cần IP Việt Nam)
# ─────────────────────────────────────────────────────────────────────────────

def crawl_phucanh():
    print("\n[13/13] PHUCANH ...", flush=True)
    BASE = "https://www.phucanh.vn"
    START_URLS = [
        f"{BASE}/may-tinh-xach-tay-laptop.html",
        f"{BASE}/may-tinh-xach-tay-laptop-dell.html",
        f"{BASE}/may-tinh-xach-tay-laptop-asus.html",
        f"{BASE}/may-tinh-xach-tay-laptop-hp.html",
        f"{BASE}/may-tinh-xach-tay-laptop-acer.html",
        f"{BASE}/may-tinh-xach-tay-laptop-lenovo.html",
        f"{BASE}/may-tinh-xach-tay-laptop-msi.html",
        f"{BASE}/laptop-lg.html",
        f"{BASE}/laptop-apple.html",
    ]
    PRODUCT_RE = re.compile(r"/[a-z0-9\-]+\.html$", re.IGNORECASE)
    CAT_RE = re.compile(
        r"/(may-tinh-xach-tay-laptop|laptop-lg|laptop-apple|laptop-gaming|"
        r"laptop-van-phong|laptop-mong-nhe|laptop-cao-cap)(-[a-z]+)?\.html$",
        re.IGNORECASE
    )

    import unicodedata
    def contains_laptop(name):
        base = "".join(c for c in unicodedata.normalize("NFKD", name.lower())
                       if not unicodedata.combining(c))
        return "laptop" in base or "may tinh xach tay" in base or "macbook" in base

    session = requests.Session()
    session.headers.update({
        "Referer": "https://www.phucanh.vn/",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    })

    products = []
    seen = set()

    for start_url in START_URLS:
        cat_name = start_url.split("/")[-1]
        for page in range(1, 30):
            url = start_url if page == 1 else f"{start_url}?page={page}"
            soup = get_soup(url, session, timeout=25)
            if not soup:
                log("PHUCANH", f"{cat_name} p{page}: failed (blocked or timeout)")
                break

            title_tag = soup.find("title")
            if title_tag and ("403" in title_tag.get_text() or "blocked" in title_tag.get_text().lower()):
                log("PHUCANH", "Blocked! Try running with VPN or from Vietnam IP.")
                return dedup(products)

            added = 0
            for sel in ["li.product-item", ".product-item", ".item-product", "article"]:
                items = soup.select(sel)
                if not items:
                    continue
                for item in items:
                    a = (item.select_one("a.product-item-link") or
                         item.select_one("h3 a") or item.select_one("h2 a") or
                         item.find("a", href=True))
                    if not a:
                        continue
                    href = (a.get("href") or "").strip()
                    if not href or not PRODUCT_RE.search(href) or CAT_RE.search(href):
                        continue
                    name_el = (item.select_one(".product-item-name") or
                               item.select_one(".product-name") or
                               item.find("h2") or item.find("h3"))
                    name = clean(name_el.get_text()) if name_el else clean(a.get_text())
                    if not name or len(name) < 5 or not contains_laptop(name):
                        continue
                    link = urljoin(BASE, href)
                    if link not in seen:
                        seen.add(link)
                        products.append({"name": name, "url": link})
                        added += 1
                if added > 0:
                    break

            log("PHUCANH", f"{cat_name} p{page}: {added} (total {len(products)})")
            if added == 0:
                break
            sleep(1.0)

    products = dedup(products)
    log("PHUCANH", f"→ {len(products)} sản phẩm")
    return products


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

CRAWLERS = {
    "gearvn":        crawl_gearvn,
    "xgear":         crawl_xgear,
    "tinhocngoisao": crawl_tinhocngoisao,
    "hangchinhhieu": crawl_hangchinhhieu,
    "laptopnew":     crawl_laptopnew,
    "memoryzone":    crawl_memoryzone,
    "cellphones":    crawl_cellphones,
    "hoanghamobile": crawl_hoanghamobile,
    "laptopworld":   crawl_laptopworld,
    "laptop88":      crawl_laptop88,
    "anphatpc":      crawl_anphatpc,
    "hacom":         crawl_hacom,
    "phucanh":       crawl_phucanh,
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global DELAY

    parser = argparse.ArgumentParser(
        description="Vietnam Laptop Crawler v2.2 - Thu thập dữ liệu laptop từ 13 website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--sites", nargs="+", choices=list(CRAWLERS.keys()),
        help="Chỉ crawl các site được chỉ định (mặc định: tất cả)"
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Tên file CSV đầu ra (mặc định: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help=f"Delay giữa các request (giây, mặc định: {DEFAULT_DELAY})"
    )
    parser.add_argument(
        "--no-playwright", action="store_true",
        help="Bỏ qua cellphones và hacom (cần Playwright)"
    )
    parser.add_argument(
        "--no-wayback", action="store_true",
        help="(Không còn dùng - giữ lại để tương thích ngược)"
    )
    args = parser.parse_args()

    DELAY = args.delay
    sites_to_crawl = args.sites if args.sites else list(CRAWLERS.keys())

    if args.no_playwright:
        for s in ["cellphones", "hacom"]:
            if s in sites_to_crawl:
                sites_to_crawl.remove(s)
        print("[INFO] Skipping Playwright sites: cellphones, hacom")

    print(f"\n{'='*60}")
    print(f"Vietnam Laptop Crawler v2.2")
    print(f"Sites  : {', '.join(sites_to_crawl)}")
    print(f"Output : {args.output}")
    print(f"Delay  : {DELAY}s")
    print(f"{'='*60}")

    all_products = []
    results = {}

    for site in sites_to_crawl:
        crawler = CRAWLERS[site]
        try:
            products = crawler()
            results[site] = products
            all_products.extend(products)
            save_csv(dedup(all_products), args.output)
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted. Saving current results...")
            break
        except Exception as e:
            print(f"\n  ✗ {site}: {e}", flush=True)
            results[site] = []

    final = dedup(all_products)
    save_csv(final, args.output)

    print(f"\n{'='*60}")
    print("TỔNG KẾT:")
    for site in sites_to_crawl:
        count = len(results.get(site, []))
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {site:25s}: {count:5d} sản phẩm")
    print(f"\n  TỔNG CỘNG: {len(final):,} sản phẩm")
    print(f"  File     : {args.output}")
    print(f"{'='*60}")

    return final


if __name__ == "__main__":
    main()
