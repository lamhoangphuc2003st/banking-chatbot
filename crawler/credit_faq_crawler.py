import requests
from bs4 import BeautifulSoup
import html
import json
import time
import random

# =====================================
# CONFIG
# =====================================
BASE_API = "https://www.vietcombank.com.vn/vi-VN/sxa/searchapi/customresults/"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest"
}

PARAMS = {
    "l": "vi-VN",
    "s": "{82EC28D2-3960-4AF6-9972-4329D4E919BF}",
    "itemid": "{E2618A51-E3EC-4F18-A903-101481A04484}",
    "autoFireSearch": "true",
    "questiontype": "Thẻ tín dụng",
    "comp": "faq_ls_tp",
    "v": "{D05CA981-35EC-434B-BC33-14B3D73A0316}",
    "p": 10,
    "o": "SortOrder,Ascending"
}

OUTPUT_FILE = "credit_faq.json"


# =====================================
# CLEAN TEXT
# =====================================
def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = BeautifulSoup(text, "lxml").get_text("\n", strip=True)
    return text.strip()


# =====================================
# PARSE HTML
# =====================================
def parse_html_block(html_block):

    soup = BeautifulSoup(html_block, "lxml")

    question_tag = soup.select_one(".field-heading")
    answer_tag = soup.select_one(".field-content")

    question = clean_text(question_tag.get_text()) if question_tag else ""
    answer = clean_text(answer_tag.get_text()) if answer_tag else ""

    return question, answer


# =====================================
# CALL API
# =====================================
def call_api(offset=0):
    params = PARAMS.copy()
    params["e"] = offset

    response = requests.get(BASE_API, headers=HEADERS, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


# =====================================
# MAIN CRAWL
# =====================================
def crawl_all():

    print("Getting first page...")
    first_page = call_api(offset=0)

    total = first_page.get("Count", 0)
    print("Total FAQ:", total)

    all_faq = []
    offset = 0

    while offset < total:

        print(f"Crawling offset {offset}")
        data = call_api(offset)

        for item in data.get("Results", []):
            html_block = item.get("Html", "")
            question, answer = parse_html_block(html_block)

            if question:
                all_faq.append({
                    "id": item.get("Id"),
                    "url": "https://www.vietcombank.com.vn" + item.get("Url", ""),
                    "question": question,
                    "answer": answer
                })

        offset += PARAMS["p"]
        time.sleep(random.uniform(1, 2))

    return all_faq


# =====================================
# RUN
# =====================================
if __name__ == "__main__":

    faq_data = crawl_all()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(faq_data, f, ensure_ascii=False, indent=2)

    print("Saved:", len(faq_data), "FAQ")
    print("File:", OUTPUT_FILE)