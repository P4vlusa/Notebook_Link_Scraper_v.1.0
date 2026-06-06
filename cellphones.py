# -*- coding: utf-8 -*-
"""
CellphoneS laptop crawler (GitHub-compatible)
- Crawl 6 brands
- Infinite scroll + click "Xem thêm"
- Extract product name + URL
- Save to output/cellphones.csv
"""

import time
import os
import pandas as pd
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup


BRANDS = {
    "Asus": "https://cellphones.com.vn/laptop/asus.html",
    "HP": "https://cellphones.com.vn/laptop/hp.html",
    "Lenovo": "https://cellphones.com.vn/laptop/lenovo.html",
    "Acer": "https://cellphones.com.vn/laptop/acer.html",
    "Dell": "https://cellphones.com.vn/laptop/dell.html",
    "MSI": "https://cellphones.com.vn/laptop/msi.html"
}

MAX_SCROLL = 40
SCROLL_PAUSE = 1.0


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,5000")
    opts.add_argument("--user-agent=Mozilla/5.0 (compatible; cps-collector/1.0)")
    return webdriver.Chrome(options=opts)


def scroll_and_expand(driver):
    """Scroll + click 'Xem thêm' until no more content loads."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    stuck = 0

    for _ in range(MAX_SCROLL):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        # Click "Xem thêm"
        try:
            buttons = driver.find_elements(By.XPATH, "//button|//a")
            for b in buttons:
                txt = (b.text or "").strip().lower()
                if txt.startswith("xem thêm"):
                    try:
                        driver.execute_script("arguments[0].click();", b)
                        time.sleep(1)
                    except:
                        pass
        except:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        stuck = stuck + 1 if new_height == last_height else 0
        last_height = new_height

        if stuck >= 3:
            break


def extract_links(driver, url, brand):
    driver.get(url)
    time.sleep(2)

    scroll_and_expand(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)

        if not href or not text:
            continue

        if ".html" not in href:
            continue

        if any(x in href for x in ["tin-tuc", "sforum", "huong-dan"]):
            continue

        if "macbook" in text.lower() or "apple" in text.lower():
            continue

        full = href if href.startswith("http") else urljoin("https://cellphones.com.vn", href)

        items.append({
            "brand": brand,
            "name": text.split("\n")[0].strip(),
            "url": full
        })

    return items


def main():
    driver = make_driver()
    final = []

    try:
        for brand, url in BRANDS.items():
            print(f"[INFO] Crawling {brand}...")
            items = extract_links(driver, url, brand)
            final.extend(items)
            print(f"[INFO] {brand}: {len(items)} items")
    finally:
        driver.quit()

    df = pd.DataFrame(final)
    df["name"] = df["name"].apply(lambda x: x.split(" - ")[0].strip())
    df = df.drop_duplicates(subset=["url"])
    df = df[df["name"].str.len() > 15]

    os.makedirs("output", exist_ok=True)
    df.to_csv("output/cellphones.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(df)} products to output/cellphones.csv")


if __name__ == "__main__":
    main()
