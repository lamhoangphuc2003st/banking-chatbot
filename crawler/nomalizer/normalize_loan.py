import json
import re
from typing import List, Dict, Any, Optional


INPUT_FILE = "../data/raw/vietcombank_loans.json"
OUTPUT_FILE = "../data/normalized/vietcombank_loans_normalized.json"


# ===============================
# Utility
# ===============================

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def extract_first_number(text: str) -> Optional[int]:
    match = re.search(r"\d+", text.replace(".", ""))
    return int(match.group()) if match else None


def extract_percentage(text: str) -> Optional[float]:
    match = re.search(r"(\d+)\s*%", text)
    return int(match.group(1)) / 100 if match else None


# ===============================
# BUILD FULL TEXT (RAG READY)
# ===============================

def build_full_text(detail: Dict[str, Any]) -> str:
    lines = []

    title = detail.get("title")
    if title:
        lines.append(f"title: {title}")

    for section_name, section_content in detail.items():
        if isinstance(section_content, dict):
            for subsection, values in section_content.items():
                if isinstance(values, list):
                    for v in values:
                        lines.append(f"{section_name} - {subsection}: {v}")

    return "\n".join(lines)


# ===============================
# AGE PARSING
# ===============================

def parse_age_conditions(text_list: List[str]) -> Dict[str, Optional[int]]:
    min_age = None
    max_age = None

    for text in text_list:
        t = text.lower()

        match_range = re.search(r"từ\s+(\d+).*?(?:đến|-)\s*(\d+)\s*tuổi", t)
        if match_range:
            min_age = int(match_range.group(1))
            max_age = int(match_range.group(2))
            continue

        match_combo = re.search(r"từ\s+(\d+)\s+tuổi.*?không quá\s+(\d+)\s+tuổi", t)
        if match_combo:
            min_age = int(match_combo.group(1))
            max_age = int(match_combo.group(2))
            continue

        match_max = re.search(r"không quá\s+(\d+)\s+tuổi", t)
        if match_max:
            max_age = int(match_max.group(1))
            continue

        match_min = re.search(r"từ\s+(\d+)\s+tuổi\s+trở lên", t)
        if match_min:
            min_age = int(match_min.group(1))
            continue

    if min_age and max_age and max_age < min_age:
        max_age = None

    return {"min_age": min_age, "max_age": max_age}


# ===============================
# TERM
# ===============================

def parse_term(text_list: List[str]) -> Dict[str, Optional[Any]]:
    max_term_months = None
    term_type = "fixed"

    for text in text_list:
        t = text.lower()

        if "thỏa thuận" in t:
            return {"max_term_months": None, "term_type": "negotiated"}

        if "năm" in t:
            years = extract_first_number(t)
            if years:
                max_term_months = years * 12

        if "tháng" in t:
            months = extract_first_number(t)
            if months:
                max_term_months = months

    return {"max_term_months": max_term_months, "term_type": term_type}


# ===============================
# LOAN RATIO
# ===============================

def parse_loan_ratio(text_list: List[str]) -> Dict[str, Optional[Any]]:
    max_loan_ratio = None
    max_loan_ratio_basis = None

    for text in text_list:
        ratio = extract_percentage(text)
        if ratio:
            max_loan_ratio = ratio
            t = text.lower()

            if "giá trị xe" in t or "giá trị căn nhà" in t:
                max_loan_ratio_basis = "property_value"
            elif "phương án" in t:
                max_loan_ratio_basis = "loan_plan"
            elif "chi phí" in t:
                max_loan_ratio_basis = "project_cost"
            else:
                max_loan_ratio_basis = "unknown"

    return {
        "max_loan_ratio": max_loan_ratio,
        "max_loan_ratio_basis": max_loan_ratio_basis,
    }


# ===============================
# COLLATERAL
# ===============================

def parse_collateral(text_list: List[str]) -> Dict[str, Any]:
    collateral_required = False
    collateral_types = set()

    for text in text_list:
        t = text.lower()
        if "tài sản bảo đảm" in t:
            collateral_required = True

            if "bất động sản" in t:
                collateral_types.add("real_estate")
            if "ô tô" in t:
                collateral_types.add("car")
            if "giấy tờ có giá" in t:
                collateral_types.add("valuable_papers")

    return {
        "collateral_required": collateral_required,
        "collateral_types": list(collateral_types),
    }


# ===============================
# CATEGORY
# ===============================

def map_loan_category(loan_type: str) -> str:
    t = loan_type.lower()

    if "bất động sản" in t:
        return "real_estate"
    if "kinh doanh" in t:
        return "business"
    if "tiêu dùng" in t:
        return "consumer"
    if "ô tô" in t:
        return "consumer"
    return "other"


# ===============================
# NORMALIZE
# ===============================

def normalize_loan(raw_loan: Dict[str, Any]) -> Dict[str, Any]:
    detail = raw_loan.get("detail", {})
    info = detail.get("Thông tin chung", {})

    all_texts = []
    for value in info.values():
        if isinstance(value, list):
            all_texts.extend(value)

    age_data = parse_age_conditions(all_texts)

    term_data = parse_term(
        info.get("Thời hạn vay tối đa", []) +
        info.get("Thời gian vay tối đa", [])
    )

    ratio_data = parse_loan_ratio(
        info.get("Số tiền vay tối đa", []) +
        info.get("Số tiền cho vay tối đa", [])
    )

    collateral_data = parse_collateral(all_texts)

    structured_features = {
        "loan_category": map_loan_category(raw_loan.get("loan_type", "")),
        "min_age": age_data["min_age"],
        "max_age": age_data["max_age"],
        "max_term_months": term_data["max_term_months"],
        "term_type": term_data["term_type"],
        "max_loan_ratio": ratio_data["max_loan_ratio"],
        "max_loan_ratio_basis": ratio_data["max_loan_ratio_basis"],
        "collateral_required": collateral_data["collateral_required"],
        "collateral_types": collateral_data["collateral_types"],
    }

    return {
        "bank": "vietcombank",
        "product_id": slugify(raw_loan.get("name", "")),
        "product_type": "loan",
        "name": raw_loan.get("name"),
        "url": raw_loan.get("url"),
        "structured_features": structured_features,
        "full_text": build_full_text(detail)
    }


# ===============================
# MAIN
# ===============================

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    normalized = [normalize_loan(loan) for loan in raw_data]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Normalized {len(normalized)} loans → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()