import requests
from bs4 import BeautifulSoup
import html
import json
import time
import random

# =========================
# CONFIG
# =========================
BASE_FACET_API = "https://www.vietcombank.com.vn/sxa/searchapi/customfacets/"
BASE_RESULT_API = "https://www.vietcombank.com.vn/vi-VN/sxa/searchapi/customresults/"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest"
}

SEARCH_ID = "{82EC28D2-3960-4AF6-9972-4329D4E919BF}"
ITEM_ID = "{2B88ACA5-3661-4FC6-8FE9-84BE38EA82B4}"
VERSION_ID = "{D05CA981-35EC-434B-BC33-14B3D73A0316}"

OUTPUT_FILE = "vietcombank_faq.json"


# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    return text.strip()


# =========================
# GET ALL QUESTION TYPES
# =========================
def get_categories():
    params = {
        "f": "questiontype",
        "s": SEARCH_ID,
        "l": "vi-VN",
        "itemid": ITEM_ID,
        "sig": ""
    }

    r = requests.get(BASE_FACET_API, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()

    data = r.json()

    categories = []
    for facet in data.get("Facets", []):
        if facet.get("Key") == "QuestionType":
            for value in facet.get("Values", []):
                categories.append(value["Name"])

    return categories


# =========================
# GET QUESTIONS BY CATEGORY
# =========================
def get_questions_by_category(category):

    params = {
        "l": "vi-VN",
        "s": SEARCH_ID,
        "itemid": ITEM_ID,
        "sig": "",
        "autoFireSearch": "true",
        "questiontype": category,
        "comp": "faq_ls_tp",
        "v": VERSION_ID,
        "p": 50,
        "e": 0,
        "o": "Question Header,Ascending"
    }

    r = requests.get(BASE_RESULT_API, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()

    data = r.json()
    results = []

    for item in data.get("Results", []):

        soup = BeautifulSoup(item["Html"], "lxml")

        question_tag = soup.select_one(".field-heading")
        answer_tag = soup.select_one(".field-content")

        question = clean_text(question_tag.get_text()) if question_tag else ""
        answer = clean_text(answer_tag.get_text()) if answer_tag else ""

        if question and answer:
            results.append({
                "question": question,
                "answer": answer
            })

    return results


# =========================
# MAIN CRAWL
# =========================
def crawl_faq():

    print("Getting categories...")
    categories = get_categories()

    all_data = []

    for category in categories:
        print("Crawling:", category)

        try:
            questions = get_questions_by_category(category)
        except Exception as e:
            print("Error:", e)
            continue

        all_data.append({
            "category": category,
            "questions": questions
        })

        time.sleep(random.uniform(1, 2))

    return all_data


if __name__ == "__main__":

    data = crawl_faq()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Saved to:", OUTPUT_FILE)