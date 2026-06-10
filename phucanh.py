# -*- coding: utf-8 -*-
"""
PhucAnh laptop crawler (Selenium version - works 100%)
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


BASE = "https://www.phucanh.vn/may-tinh-xach-tay-laptop.html"


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,6000")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def scroll_all(driver):
    """Scroll toàn trang để load hết sản phẩm."""
    last_height = 0
    while True:
        driver.execute_script("window.scrollBy(0, 1500);")
        time.sleep(1.2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def extract_products(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    # Layout mới của Phúc Anh
    for box in soup.select(".product-item"):
        a = box.select_one("a")
        if not a:
            continue

        name = a.get("title") or a.get_text(strip=True)
        href = a.get("href")

        if not name or not href:
            continue

        full = urljoin("https://www.phucanh.vn", href)

        items.append({
            "name": name.strip(),
            "url": full
        })

    return items


def main():
    driver = make_driver()
    driver.get(BASE)
    time.sleep(2)

    print("[INFO] Scrolling...")
    scroll_all(driver)

    print("[INFO] Extracting products...")
    items = extract_products(driver)

    driver.quit()

    os.makedirs("output", exist_ok=True)
    out_file = "output/phucanh.csv"

    df = pd.DataFrame(items)
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"[DONE] Total {len(df)} items → {out_file}")


if __name__ == "__main__":
    main()
