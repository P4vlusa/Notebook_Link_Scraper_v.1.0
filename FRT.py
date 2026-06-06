# -*- coding: utf-8 -*-
"""
FPT Shop laptop crawler
- Crawl 7 brands
- Infinite scroll + click "Xem thêm"
- Extract product name + URL
- Save to output/fpt.csv
"""

import time
import os
import pandas as pd
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


def crawl_brand(driver, brand_url, brand_name):
    print(f"\n--- Đang quét hãng: {brand_name.upper()} ---")
    print(f"Link: {brand_url}")

    try:
        driver.get(brand_url)
        time.sleep(3)

        click_count = 0
        while True:
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                load_more_btn = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//a[contains(text(), 'Xem thêm') or contains(@class, 'view-more')]"
                            " | //button[contains(text(), 'Xem thêm')]",
                        )
                    )
                )

                if not load_more_btn.is_displayed():
                    break

                driver.execute_script("arguments[0].click();", load_more_btn)
                click_count += 1
                print(f"  -> Đã bấm 'Xem thêm' lần {click_count}...")
                time.sleep(3)

                if click_count > 20:
                    break

            except:
                break

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = []

        for link in soup.find_all("a", href=True):
            href = link["href"]

            if "/may-tinh-xach-tay/" in href and "?" not in href and len(href) > 30:
                name = link.get("title")
                if not name:
                    h3 = link.find("h3")
                    name = h3.get_text(strip=True) if h3 else link.get_text(strip=True)

                if not name or "macbook" in name.lower() or "apple" in name.lower():
                    continue

                full_link = href if href.startswith("http") else "https://fptshop.com.vn" + href

                items.append(
                    {
                        "brand": brand_name,
                        "name": name,
                        "url": full_link,
                    }
                )

        print(f"  -> Tìm thấy {len(items)} sản phẩm của {brand_name}.")
        return items

    except Exception as e:
        print(f"  -> Lỗi khi quét {brand_name}: {e}")
        return []


def main():
    brand_urls = {
        "Asus": "https://fptshop.com.vn/may-tinh-xach-tay/asus",
        "MSI": "https://fptshop.com.vn/may-tinh-xach-tay/msi",
        "HP": "https://fptshop.com.vn/may-tinh-xach-tay/hp",
        "Lenovo": "https://fptshop.com.vn/may-tinh-xach-tay/lenovo",
        "Acer": "https://fptshop.com.vn/may-tinh-xach-tay/acer",
        "Dell": "https://fptshop.com.vn/may-tinh-xach-tay/dell",
        "Gigabyte": "https://fptshop.com.vn/may-tinh-xach-tay/gigabyte",
    }

    driver = get_driver()
    all_products = []

    try:
        for brand_name, url in brand_urls.items():
            products = crawl_brand(driver, url, brand_name)
            all_products.extend(products)
    finally:
        driver.quit()

    if all_products:
        df = pd.DataFrame(all_products)
        df = df.drop_duplicates(subset=["url"])
        df = df.sort_values(by=["brand", "name"])

        os.makedirs("output", exist_ok=True)
        df.to_csv("output/fpt.csv", index=False, encoding="utf-8-sig")

        print("\n====================================")
        print(f"TỔNG KẾT: {len(df)} sản phẩm (đã loại MacBook)")
        print("File:", "output/fpt.csv")
        print("====================================")
    else:
        print("Không lấy được dữ liệu nào.")


if __name__ == "__main__":
    main()
