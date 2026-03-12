import requests
from bs4 import BeautifulSoup
import html
import time
import random
import json
import re

BASE_FACET_API = "https://www.vietcombank.com.vn/vi-VN/sxa/searchapi/customfacets/"
BASE_RESULT_API = "https://www.vietcombank.com.vn/vi-VN/sxa/searchapi/customresults/"
BASE_DOMAIN = "https://www.vietcombank.com.vn"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest"
}


# ===============================
# Clean text (remove toggle words)
# ===============================
def clean_text(text):
    text = re.sub(r'Xem thêm|Thu gọn|Mở rộng', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ===============================
# 1. Get loan types
# ===============================
def get_loan_types():
    params = {
        "f": "loantype",
        "s": "{BD096303-44C1-4253-8C7C-D79CC04E9C1F}",
        "l": "vi-VN",
        "itemid": "{69441009-8E89-47B1-AB22-A1BD74B17518}",
        "sig": "loan-list"
    }

    r = requests.get(BASE_FACET_API, headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    facets = data.get("Facets", [])
    if not facets:
        return []

    return [v["Name"] for v in facets[0].get("Values", [])]


# ===============================
# 2. Get product list
# ===============================
def get_products(loan_type):
    params = {
        "l": "vi-VN",
        "s": "{BD096303-44C1-4253-8C7C-D79CC04E9C1F}",
        "itemid": "{69441009-8E89-47B1-AB22-A1BD74B17518}",
        "sig": "loan-list",
        "loantype": loan_type,
        "p": "6",
        "o": "SortOrder,Ascending",
        "v": "{E1DB4CC4-AE84-4BA5-A0F2-2D5EA68E82D4}"
    }

    r = requests.get(BASE_RESULT_API, headers=HEADERS, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    products = []

    for item in data.get("Results", []):
        soup = BeautifulSoup(item.get("Html", ""), "lxml")

        name_tag = soup.select_one(".card-name a")
        name = html.unescape(name_tag.get_text(strip=True)) if name_tag else None

        products.append({
            "loan_type": loan_type,
            "name": name,
            "url": BASE_DOMAIN + item.get("Url", "")
        })

    return products


# ===============================
# 3. Get full detail
# ===============================
def get_full_product_detail(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    data = {}

    title_tag = soup.select_one("h1")
    data["title"] = title_tag.get_text(strip=True) if title_tag else None

    content_wrappers = soup.select(".content-wrapper")

    for wrapper in content_wrappers:

        tab_index = wrapper.get("data-index", "")
        tab_name_tag = soup.select_one(f'.select-item[data-index="{tab_index}"]')

        tab_name = tab_name_tag.get_text(strip=True) if tab_name_tag else f"tab_{tab_index}"

        tab_data = {}

        items = wrapper.select(".content-item")

        for item in items:

            name_tag = item.select_one(".name")
            label_tag = item.select_one(".label")

            if not name_tag or not label_tag:
                continue

            section_title = html.unescape(name_tag.get_text(strip=True))

            values = []

            # lấy list item
            for li in label_tag.select("li"):
                text = li.get_text(" ", strip=True)
                text = clean_text(html.unescape(text))
                if text:
                    values.append(text)

            # nếu không có li
            if not values:
                raw_text = label_tag.get_text(" ", strip=True)
                raw_text = clean_text(html.unescape(raw_text))
                if raw_text:
                    values.append(raw_text)

            tab_data[section_title] = values

        if tab_data:
            data[tab_name] = tab_data

    return data


# ===============================
# 4. Full pipeline
# ===============================
def crawl_all():
    all_products = []

    loan_types = get_loan_types()

    for loan in loan_types:
        products = get_products(loan)

        for p in products:
            print("Crawling:", p["name"])

            detail = get_full_product_detail(p["url"])

            merged = {
                "loan_type": p["loan_type"],
                "name": p["name"],
                "url": p["url"],
                "detail": detail
            }

            all_products.append(merged)

            time.sleep(random.uniform(1, 2))

    return all_products


# ===============================
# 5. Run & Save
# ===============================
if __name__ == "__main__":

    data = crawl_all()

    with open("vietcombank_loans.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Saved:", len(data), "products")