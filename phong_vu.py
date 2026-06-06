# -*- coding: utf-8 -*-
"""
PhongVu laptop crawler (GitHub-compatible)
- Infinite scroll + click "Xem thêm"
- Extract product name + URL
- Save to output/phongvu.csv
"""

import time
import os
import pandas as pd
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


URL = "https://phongvu.vn/c/laptop"
MAX_SCROLL = 80
SCROLL_PAUSE = 1.5


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,5000")
    opts.add_argument("--user-agent=Mozilla/5.0 (compatible; pv-collector/1.0)")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def scroll_and_expand(driver):
    """Scroll + click 'Xem thêm' until no more content loads."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    stuck = 0

    for _ in range(MAX_SCROLL):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(SCROLL_PAUSE)

        # Click "Xem thêm"
        try:
            buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Xem thêm')]")
            for b in buttons:
                if b.is_displayed():
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(2)
        except:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        stuck = stuck + 1 if new_height == last_height else 0
        last_height = new_height

        if stuck >= 4:
            break


def extract_links(driver):
    driver.get(URL)
    time.sleep(3)

    scroll_and_expand(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        name = a.get_text(" ", strip=True)

        if not href or not name:
            continue

        # Filter product links
        if "-" in href and "/c/" not in href and len(name) > 20:
            if any(bad in href for bad in ["tin-tuc", "hoi-dap", "khuyen-mai", "build-pc"]):
                continue

            full = href if href.startswith("http") else "https://phongvu.vn" + href

            items.append({
                "name": name,
                "url": full
            })

    return items


def main():
    driver = make_driver()
    final = []

    try:
        print("[INFO] Crawling PhongVu...")
        final = extract_links(driver)
    finally:
        driver.quit()

    df = pd.DataFrame(final)
    df = df.drop_duplicates(subset=["url"])
    df = df[df["name"].str.len() > 15]

    os.makedirs("output", exist_ok=True)
    df.to_csv("output/phongvu.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(df)} products to output/phongvu.csv")


if __name__ == "__main__":
    main()
