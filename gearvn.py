# -*- coding: utf-8 -*-
"""
GEARVN laptop crawler
- Collects all laptop product URLs
- Extracts product name (H1)
- Saves to output/gearvn.csv
"""

import argparse, time
from urllib.parse import urljoin, urlparse
import os

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

SEED_ALL = "https://gearvn.com/collections/laptop"
DEALER   = "GEARVN"

MAX_SCROLLS  = 600
SCROLL_PAUSE = 0.8
PAGE_PAUSE   = 0.7


def make_driver(headful=False):
    opts = Options()
    if not headful:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,4200")
    opts.add_argument("--user-agent=Mozilla/5.0 (compatible; gearvn-collector/1.0)")
    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(60)
    drv.set_script_timeout(60)
    return drv


def same_site(u: str) -> bool:
    try:
        return urlparse(u).netloc.endswith("gearvn.com")
    except:
        return False


def expand_listing(driver):
    time.sleep(2)
    last_h = driver.execute_script("return document.body.scrollHeight")
    stagnant = 0

    for _ in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        # click "Xem thêm"
        try:
            for el in driver.find_elements(By.XPATH, "//button|//a"):
                txt = (el.text or "").strip().lower()
                if txt.startswith("xem thêm"):
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(SCROLL_PAUSE)
                    except:
                        pass
        except:
            pass

        new_h = driver.execute_script("return document.body.scrollHeight")
        stagnant = stagnant + 1 if new_h == last_h else 0
        last_h = new_h

        if stagnant >= 3:
            break


def collect_listing_links(driver, seed_url: str):
    driver.get(seed_url)
    expand_listing(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("/"):
            href = urljoin(seed_url, href)

        path = urlparse(href).path

        if (same_site(href)
            and path.startswith("/products/")
            and path.count("/") >= 2
            and not any(seg in path for seg in ("/blogs", "/pages", "/collections"))):
            links.add(href)

    return sorted(links)


def extract_product(driver, url: str):
    try:
        driver.get(url)
    except WebDriverException:
        return None

    time.sleep(PAGE_PAUSE)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    def text_of(el):
        return " ".join(el.get_text(" ", strip=True).split()) if el else None

    name = text_of(soup.find("h1")) or text_of(soup.find("h2"))

    if not name:
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            name = og["content"].strip()

    if not name:
        name = text_of(soup.find("title"))

    if not name:
        return None

    return {
        "name": name,
        "dealer": DEALER,
        "url": url
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--brand", type=str)
    args = ap.parse_args()

    seed = args.brand.strip() if args.brand else SEED_ALL
    driver = make_driver(headful=args.headful)

    try:
        print(f"[INFO] Loading listing: {seed}")
        links = collect_listing_links(driver, seed)
        print(f"[INFO] Found {len(links)} product links")

        out, seen = [], set()

        for i, u in enumerate(links, 1):
            if u in seen:
                continue
            seen.add(u)

            rec = extract_product(driver, u)
            if rec:
                out.append(rec)

            if i % 25 == 0:
                print(f"[INFO] Checked {i}/{len(links)}")

    finally:
        try:
            driver.quit()
        except:
            pass

    # SAVE TO output/gearvn.csv
    os.makedirs("output", exist_ok=True)
    df = pd.DataFrame(out)
    df.to_csv("output/gearvn.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(out)} products to output/gearvn.csv")


if __name__ == "__main__":
    main()
