import requests
from bs4 import BeautifulSoup
import html
import json
import math
import time
import random
import re

# =====================================================
# CONFIG
# =====================================================
BASE_API = "https://www.vietcombank.com.vn/vi-VN/sxa/searchapi/customresults/"
BASE_DOMAIN = "https://www.vietcombank.com.vn"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest"
}

PAGE_SIZE = 6
OUTPUT_FILE = "vietcombank_credit_cards.json"


# =====================================================
# CLEAN TEXT
# =====================================================
def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r'\(chi tiết\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Xem thêm|Thu gọn|Mở rộng', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# =====================================================
# CALL CARD LIST API (PHÂN TRANG)
# =====================================================
def call_api(offset=0):

    params = {
        "l": "vi-VN",
        "s": "{5BFF185D-F650-4A6C-A2A1-D26C58B43C15}",
        "itemid": "{967D60F8-65BA-4CEB-AEB4-E74845673377}",
        "sig": "card-list",
        "type": "Thẻ tín dụng",
        "p": PAGE_SIZE,
        "o": "SortOrder,Ascending",
        "v": "{755FF168-E210-47C4-9122-97730FC37054}"
    }

    if offset > 0:
        params["e"] = offset

    r = requests.get(BASE_API, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# =====================================================
# PARSE CARD BASIC INFO (LIST PAGE)
# =====================================================
def parse_card_basic(item):

    soup = BeautifulSoup(item.get("Html", ""), "lxml")

    name_tag = soup.select_one(".card-name a")
    name = clean_text(name_tag.get_text()) if name_tag else None

    tag_tag = soup.select_one(".card-tag .chip")
    tag = clean_text(tag_tag.get_text()) if tag_tag else None

    features = {}
    for feature in soup.select(".feature"):
        fname = feature.select_one(".feature-name")
        fvalue = feature.select_one(".feature-value")
        if fname and fvalue:
            features[clean_text(fname.get_text())] = clean_text(fvalue.get_text())

    open_btn = soup.select_one(".card-actions a.btn")
    open_link = open_btn["href"] if open_btn else None

    return {
        "id": item.get("Id"),
        "name": name,
        "url": BASE_DOMAIN + item.get("Url", ""),
        "tag": tag,
        "features": features,
        "open_link": open_link
    }


# =====================================================
# PARSE CARD DETAIL PAGE (4 TAB)
# =====================================================
def get_card_detail(url):

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    result = {}

    title_tag = soup.select_one("h1")
    result["title"] = clean_text(title_tag.get_text()) if title_tag else None

    tab_wrappers = soup.select(".component-content .content-wrapper")

    for wrapper in tab_wrappers:

        tab_index = wrapper.get("data-index", "")

        tab_name_tag = soup.select_one(f'.select-item[data-index="{tab_index}"]')
        tab_name = clean_text(tab_name_tag.get_text()) if tab_name_tag else f"tab_{tab_index}"

        tab_data = {}

        content_items = wrapper.select(".content-item")

        for item in content_items:

            section_title_tag = item.select_one(".name")
            if not section_title_tag:
                continue

            section_title = clean_text(section_title_tag.get_text())

            values = []
            label_tag = item.select_one(".label")

            if label_tag:

                # 1️⃣ Ưu tiên li
                li_tags = label_tag.select("li")
                if li_tags:
                    for li in li_tags:
                        text = clean_text(li.get_text(" ", strip=True))
                        if text:
                            values.append(text)

                else:
                    # 2️⃣ Nếu không có li thì lấy p
                    p_tags = label_tag.select("p")
                    if p_tags:
                        for p in p_tags:
                            text = clean_text(p.get_text(" ", strip=True))
                            if text:
                                values.append(text)
                    else:
                        # 3️⃣ Nếu không có p/li thì lấy document
                        doc_tags = label_tag.select(".document")
                        for doc in doc_tags:
                            text = clean_text(doc.get_text(" ", strip=True))
                            if text:
                                values.append(text)

            else:
                # Trường hợp text nằm trực tiếp
                full_text = item.get_text(" ", strip=True)
                full_text = full_text.replace(section_title, "", 1)
                full_text = clean_text(full_text)

                if full_text:
                    values.append(full_text)

            if values:
                tab_data[section_title] = values

        if tab_data:
            result[tab_name] = tab_data

    return result


# =====================================================
# FULL PIPELINE
# =====================================================
def crawl_all_cards():

    print("Getting first page...")
    first_page = call_api(offset=0)

    total = first_page.get("Count", 0)
    print("Total cards:", total)

    total_pages = math.ceil(total / PAGE_SIZE)
    all_cards = []

    for page in range(total_pages):

        offset = page * PAGE_SIZE
        print(f"\nCrawling list offset {offset}")

        data = call_api(offset=offset)

        for item in data.get("Results", []):

            basic = parse_card_basic(item)

            print("   Crawling detail:", basic["name"])

            try:
                detail = get_card_detail(basic["url"])
                basic["detail"] = detail
            except Exception as e:
                print("   ERROR:", e)
                basic["detail"] = None

            all_cards.append(basic)
            time.sleep(random.uniform(1, 2))

    return all_cards


if __name__ == "__main__":

    cards = crawl_all_cards()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    print("\nSaved:", len(cards), "cards")
    print("File:", OUTPUT_FILE)