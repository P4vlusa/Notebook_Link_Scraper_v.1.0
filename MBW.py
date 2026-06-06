# -*- coding: utf-8 -*-
"""
TGDD laptop crawler (GitHub-compatible)
- Click "Xem thêm" until no more products
- Extract product name + URL
- Save to output/tgdd.csv
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


URL = "https://www.thegioididong.com/laptop"
BASE = "https://www.thegioididong.com"


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,5000")
    opts.add_argument("--user-agent=Mozilla/5.0 (compatible; tgdd-collector/1.0)")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def click_view_more(driver):
    """Click 'Xem thêm' until no more."""
    click_count = 0

    while True:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, ".view-more a")
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                click_count += 1
                print(f"[INFO] Click 'Xem thêm' lần {click_count}")
                time.sleep(2)
            else:
                break
        except:
            break


def extract_products(driver):
    driver.get(URL)
    time.sleep(3)

    click_view_more(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    for li in soup.select("ul.listproduct li.item"):
        try:
            a = li.find("a", class_="main-contain")
            if not a:
                continue

            name_tag = a.find("h3")
            name = name_tag.text.strip() if name_tag else None

            href = a.get("href")
            if not href:
                continue

            full = BASE + href if not href.startswith("http") else href

            if "/laptop/" not in full:
                continue

            items.append({
                "name": name,
                "url": full
            })

        except:
            continue

    return items


def main():
    driver = make_driver()
    final = []

    try:
        print("[INFO] Crawling TGDD...")
        final = extract_products(driver)
    finally:
        driver.quit()

    df = pd.DataFrame(final)
    df = df.drop_duplicates(subset=["url"])
    df = df[df["name"].str.len() > 10]

    os.makedirs("output", exist_ok=True)
    df.to_csv("output/tgdd.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(df)} products to output/tgdd.csv")


if __name__ == "__main__":
    main()
