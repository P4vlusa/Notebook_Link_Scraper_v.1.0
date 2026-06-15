# -*- coding: utf-8 -*-
"""
PhongVu laptop crawler (stable 2025 version)
"""

import os
import time
import pandas as pd
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


URL = "https://phongvu.vn/c/laptop"


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,6000")
    opts.add_argument("--user-agent=Mozilla/5.0")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def scroll_all(driver):
    """Scroll toàn trang để load hết sản phẩm."""
    last_height = 0
    while True:
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(1.2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_products(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    # Tên sản phẩm nằm trong thẻ h3 có role="heading"
    for box in soup.select("div[data-cy='product-card']"):
        a = box.select_one("a[href]")
        name_tag = box.select_one("h3[role='heading']")

        if not a or not name_tag:
            continue

        name = name_tag.get_text(strip=True)
        href = a.get("href")

        if not name or not href:
            continue

        full = urljoin("https://phongvu.vn", href)

        items.append({
            "name": name,
            "url": full
        })

    return items


def main():
    print("[INFO] Crawling PhongVu...")

    driver = make_driver()
    driver.get(URL)
    time.sleep(2)

    scroll_all(driver)

    items = extract_products(driver)
    driver.quit()

    df = pd.DataFrame(items)

    # Chỉ lọc nếu có cột name
    if "name" in df.columns:
        df = df[df["name"].str.len() > 10]

    os.makedirs("output", exist_ok=True)
    df.to_csv("output/phongvu.csv", index=False, encoding="utf-8-sig")

    print(f"[DONE] Saved {len(df)} products to output/phongvu.csv")


if __name__ == "__main__":
    main()
