import csv
import json
from pathlib import Path

INPUT = "backend/evaluate/retrieval_test_cases.csv"
OUTPUT = "backend/evaluate/golden_dataset.json"


def normalize(row):
    return {k.strip().lower(): (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()}


def guess_category(row):
    section = row.get("section", "")
    type_ = row.get("type", "")

    if section == "list":
        return "discovery"

    if section == "__qa__":
        return "qa"

    return "product_detail"


def extract_keywords(row):
    keywords = []

    if row.get("product"):
        keywords.append(row["product"])

    if row.get("section") not in ["", "list", "__qa__"]:
        keywords.append(row["section"])

    return keywords[:3]


def main():
    dataset = []

    with open(INPUT, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        print("CSV columns:", reader.fieldnames)

        for i, raw in enumerate(reader):
            row = normalize(raw)

            case = {
                "id": f"case_{i:04d}",
                "category": guess_category(row),
                "query": row["query"],
                "expected_contains": extract_keywords(row),
                "expected_not_contains": [],
                "min_doc_ids": [row["doc_id"]],
            }

            dataset.append(case)

    print("Generated:", len(dataset))

    Path(OUTPUT).parent.mkdir(exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()