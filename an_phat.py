# -*- coding: utf-8 -*-
"""
AN PHAT laptop crawler
- Infinite scroll
- Verify price node
- Save CSV only → output/anphat.csv
"""

import argparse, sys, time, os
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

SEED_ALL = "https://www.anphatpc.com.vn/may-tinh-xach-tay-laptop.html"
BRAND_SEEDS = {
    "ASUS": "https://www.anphatpc.com.vn/laptop-asus_dm1058.html",
    "DELL": "https://www.anphatpc.com.vn/laptop-dell_dm1012.html",
    "HP": "https://www.anphatpc.com.vn/laptop-hp_dm1013.html",
    "MSI": "https://www.anphatpc.com.vn/laptop-msi_dm1065.html",
    "LENOVO": "https://www.anphatpc.com.vn/laptop-lenovo_dm1011.html",
    "ACER": "https://www.anphatpc.com.vn/laptop-acer_dm1014.html",
    "GIGABYTE": "https://www.anphatpc.com.vn/laptop-gigabyte_dm1016.html",
    "ASUS-ROG": "https://www.anphatpc.com.vn/laptop-asus-rog_dm1533.html",
}

DEALER = "AN PHAT"
PRICE_TAG = "b"
PRICE_CLASS = "text-18 js-pro-total-price"

MAX_SCROLLS = 600
SCROLL_PAUSE = 0.8
PAGE_PAUSE = 0.6


def headless_driver(headful=False):
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,4000")
    opts.add_argument("--user-agent=Mozilla/5.0 (compatible; anphat-collector/1.0)")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    return driver


def same_site(u: str) -> bool:
    try:
        return urlparse(u).netloc.endswith("anphatpc.com.vn")
    except:
        return False


def infinite_load_all(driver):
    time.sleep(2)
    last_h = driver.execute_script("return document.body.scrollHeight")
    stuck = 0

    for _ in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        # click "Xem thêm"
        try:
            for b in driver.find_elements(By.XPATH, "//button|//a"):
                txt = (b.text or "").strip().lower()
                if txt.startswith("xem thêm"):
                    try:
                        driver.execute_script("arguments[0].click();", b)
                        time.sleep(SCROLL_PAUSE)
                    except:
                        pass
        except:
            pass

        new_h = driver.execute_script("return document.body.scrollHeight")
        stuck = stuck + 1 if new_h == last_h else 0
        last_h = new_h

        if stuck >= 3:
            break


def collect_listing_links(driver, seed_url: str):
    driver.get(seed_url)
    infinite_load_all(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = set()

    selectors = [
        ".p-item a", ".product a", ".product-item a", ".p-name a",
        ".product-title a", ".list-product a"
    ]

    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            if not href:
                continue
            u = urljoin(seed_url, href)
            if (same_site(u)
                and u.endswith(".html")
                and "/tin-tuc" not in u
                and "/news" not in u
                and "/khuyen-mai" not in u
                and "/tra-cuu" not in u):
                links.add(u)

    if not links:
        for a in soup.find_all("a", href=True):
            u = urljoin(seed_url, a["href"])
            if u.endswith(".html") and same_site(u):
                links.add(u)

    return sorted(links)


def extract_verified_product(driver, url: str):
    try:
        driver.get(url)
    except WebDriverException:
        return None

    time.sleep(PAGE_PAUSE)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    price_node = soup.find(PRICE_TAG, class_=PRICE_CLASS) or \
                 soup.find(PRICE_TAG, class_=lambda c: c and "js-pro-total-price" in c)

    if not price_node:
        return None

    def text_of(el):
        return " ".join(el.get_text(" ", strip=True).split()) if el else None

    name = text_of(soup.find("h1"))
    if not name:
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            name = og["content"].strip()
    if not name:
        name = text_of(soup.find("title"))

    return {
        "name": name or "",
        "dealer": DEALER,
        "url": url,
        "tag": PRICE_TAG,
        "class_name": PRICE_CLASS,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--brand", type=str)
    args = ap.parse_args()

    seed = BRAND_SEEDS.get(args.brand.strip().upper(), SEED_ALL) if args.brand else SEED_ALL

    driver = headless_driver(headful=args.headful)
    out = []

    try:
        print(f"[INFO] Loading listing: {seed}")
        links = collect_listing_links(driver, seed)
        print(f"[INFO] Found {len(links)} product links")

        seen = set()
        for i, u in enumerate(links, 1):
            if u in seen:
                continue
            seen.add(u)

            rec = extract_verified_product(driver, u)
            if rec:
                out.append(rec)

            if i % 25 == 0:
                print(f"[INFO] Checked {i}/{len(links)}")

    finally:
        try:
            driver.quit()
        except:
            pass

    # SAVE TO output/anphat.csv
    os.makedirs("output", exist_ok=True)
    df = pd.DataFrame(out)
    df.to_csv("output/anphat.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(out)} products to output/anphat.csv")


if __name__ == "__main__":
    main()
