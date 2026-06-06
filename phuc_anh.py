# -*- coding: utf-8 -*-
"""
PhucAnh laptop crawler (GitHub-compatible)
- Crawl multiple brand URLs
- Extract product name + URL
- Save to output/phucanh.csv
"""

import csv
import re
import time
import unicodedata
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.phucanh.vn"

START_URLS = [
    f"{BASE}/may-tinh-xach-tay-laptop-dell.html",
    f"{BASE}/may-tinh-xach-tay-laptop-asus.html",
    f"{BASE}/laptop-lg.html",
    f"{BASE}/may-tinh-xach-tay-laptop-hp.html",
    f"{BASE}/may-tinh-xach-tay-laptop-acer.html",
    f"{BASE}/may-tinh-xach-tay-laptop-lenovo.html",
    f"{BASE}/may-tinh-xach-tay-laptop-msi.html",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

PRODUCT_RE = re.compile(r"/[a-z0-9\-]+\.html$", re.IGNORECASE)
CATEGORY_LIKE_RE = re.compile(r"/laptop(-[a-z0-9]+)?\.html$", re.IGNORECASE)


def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def contains_keyword(name: str) -> bool:
    base = strip_accents(name).lower()
    return "laptop" in base or "may tinh xach tay" in base


def fetch_html(url: str, retries: int = 3, timeout: int = 25) -> str:
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except:
            if i == retries - 1:
                raise
            time.sleep(1.2 * (i + 1))


def anchor_looks_like_product(a) -> bool:
    href = (a.get("
