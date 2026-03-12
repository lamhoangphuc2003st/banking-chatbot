import json
import re
from typing import Any, Dict, Optional

RAW_PATH = "../data/raw/vietcombank_credit_cards.json"
OUTPUT_PATH = "../data/normalized/vietcombank_credit_cards_normalized.json"


# ==========================================================
# UTILITIES
# ==========================================================

def clean_number(text: str) -> str:
    return text.replace(".", "").replace(",", "")


def extract_first_number(text: str) -> Optional[float]:
    if not text:
        return None

    cleaned = clean_number(text)
    numbers = re.findall(r"\d+\.?\d*", cleaned)

    if not numbers:
        return None

    return float(numbers[0])


def detect_card_brand(name: str) -> Optional[str]:
    brands = ["Visa", "Mastercard", "American Express", "JCB", "UnionPay"]
    for brand in brands:
        if brand.lower() in name.lower():
            return brand
    return None


# ==========================================================
# FEATURE EXTRACTORS
# ==========================================================

def extract_annual_fee(card):
    try:
        fee_list = card["detail"]["Biểu phí"]["Phí thường niên"]
    except KeyError:
        return None, None, None

    main_fee = None
    supp_fee = None
    waiver_threshold = None

    for item in fee_list:
        if "Thẻ chính" in item:
            main_fee = extract_first_number(item)

        if "Thẻ phụ" in item:
            supp_fee = extract_first_number(item)

        if "doanh số chi tiêu từ" in item.lower():
            number = extract_first_number(item)
            if number:
                waiver_threshold = number * 1_000_000

    return main_fee, supp_fee, waiver_threshold


def extract_credit_limit(card):
    try:
        limit_list = card["detail"]["Thông tin sản phẩm"]["Hạn mức sử dụng"]
    except KeyError:
        return None, None, None, None

    min_limit = None
    max_limit = None
    domestic_withdraw_percent = None
    foreign_daily_limit = None

    for item in limit_list:
        if "từ" in item.lower() and "triệu" in item.lower():
            min_limit = extract_first_number(item) * 1_000_000

        if "đến" in item.lower() and "triệu" in item.lower():
            max_limit = extract_first_number(item) * 1_000_000

        if "rút tiền trong nước" in item.lower() and "%" in item:
            domestic_withdraw_percent = extract_first_number(item)

        if "nước ngoài" in item.lower() and "triệu" in item.lower():
            foreign_daily_limit = extract_first_number(item) * 1_000_000

    return min_limit, max_limit, domestic_withdraw_percent, foreign_daily_limit


def extract_interest_free_days(card):
    try:
        benefits = card["detail"]["Lợi ích"]
    except KeyError:
        return None

    def search(d):
        if isinstance(d, dict):
            for v in d.values():
                result = search(v)
                if result:
                    return result
        elif isinstance(d, list):
            for item in d:
                if "Miễn lãi" in item:
                    return extract_first_number(item)
        return None

    return search(benefits)


def extract_cashback(card):
    try:
        benefits = card["detail"]["Lợi ích"]
    except KeyError:
        return None, None, None

    max_percent = None
    max_statement = None
    max_year = None

    text = json.dumps(benefits, ensure_ascii=False)

    percent_matches = re.findall(r"(\d+\.?\d*)%", text)
    if percent_matches:
        max_percent = max([float(p) for p in percent_matches])

    statement_match = re.findall(r"tối đa ([\d\.]+) VND/kỳ", text)
    if statement_match:
        max_statement = float(clean_number(statement_match[0]))

    year_match = re.findall(r"([\d\.]+) triệu VND/năm", text)
    if year_match:
        max_year = float(clean_number(year_match[0])) * 1_000_000

    return max_percent, max_statement, max_year


def extract_card_validity(card):
    try:
        validity = card["detail"]["Thông tin sản phẩm"]["Hiệu lực thẻ"][0]
    except KeyError:
        return None

    return extract_first_number(validity)


def extract_supplementary_count(card):
    try:
        count = card["detail"]["Thông tin sản phẩm"]["Số lượng thẻ phụ"][0]
    except KeyError:
        return None

    return extract_first_number(count)


# ==========================================================
# FLATTEN
# ==========================================================

def flatten_dict(data: Any, parent_key: str = "") -> str:
    lines = []

    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key} {k}".strip()
            lines.append(flatten_dict(v, new_key))

    elif isinstance(data, list):
        for item in data:
            lines.append(flatten_dict(item, parent_key))

    else:
        lines.append(f"{parent_key}: {data}")

    return "\n".join([l for l in lines if l])


# ==========================================================
# NORMALIZE
# ==========================================================

def normalize_card(card):

    main_fee, supp_fee, waiver = extract_annual_fee(card)
    min_limit, max_limit, withdraw_percent, foreign_limit = extract_credit_limit(card)
    interest_free = extract_interest_free_days(card)
    cashback_percent, cashback_statement, cashback_year = extract_cashback(card)

    normalized = {
        "product_id": f"vcb_{card.get('id')}",
        "bank_id": "vietcombank",
        "product_type": "credit_card",
        "name": card.get("name"),
        "card_brand": detect_card_brand(card.get("name", "")),
        "is_discontinued": "ngừng phát hành" in card.get("name", "").lower(),

        "structured_features": {
            "annual_fee_main": main_fee,
            "annual_fee_supplementary": supp_fee,
            "annual_fee_waiver_spending_threshold": waiver,

            "min_credit_limit": min_limit,
            "max_credit_limit": max_limit,
            "domestic_cash_withdrawal_percent": withdraw_percent,
            "foreign_cash_withdrawal_daily_limit": foreign_limit,

            "interest_free_days": interest_free,
            "card_validity_years": extract_card_validity(card),
            "max_supplementary_cards": extract_supplementary_count(card),

            "max_cashback_percent": cashback_percent,
            "max_cashback_amount_per_statement": cashback_statement,
            "max_cashback_amount_per_year": cashback_year
        },

        "full_text": flatten_dict(card.get("detail", {}))
    }

    return normalized


# ==========================================================
# MAIN
# ==========================================================

def main():
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        raw_cards = json.load(f)

    normalized_cards = [normalize_card(card) for card in raw_cards]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized_cards, f, ensure_ascii=False, indent=2)

    print(f"Normalized {len(normalized_cards)} credit cards.")


if __name__ == "__main__":
    main()