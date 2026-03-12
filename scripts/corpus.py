import json

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

credit_cards = load_json("data/normalized/vietcombank_credit_cards_normalized.json")
credit_faq = load_json("data/normalized/vietcombank_credit_faq_normalized.json")
loan_faq = load_json("data/normalized/vietcombank_loan_faq_normalized.json")
loans = load_json("data/normalized/vietcombank_loans_normalized.json")

corpus = []

# 1. Credit card products
for product in credit_cards:

    text = f"Sản phẩm: {product['name']}.\n{product['full_text']}"

    corpus.append({
        "doc_id": f"credit_product_{product['product_id']}",
        "bank": product["bank_id"],
        "product_type": "credit_card",
        "document_type": "product",
        "product_id": product["product_id"],
        "product_name": product["name"],
        "text": text,
        "metadata": {
            "source": "vietcombank_credit_cards",
            "card_brand": product["card_brand"],
            **product["structured_features"]
        }
    })


# 2. Credit card FAQ
for faq in credit_faq:

    question = faq.get("question", "")
    answer = faq.get("answer", "")

    if question and answer:
        text = f"Question: {question}\nAnswer: {answer}"
    else:
        text = faq["full_text"]

    corpus.append({
        "doc_id": f"credit_faq_{faq['faq_id']}",
        "bank": faq["bank"],
        "product_type": "credit_card",
        "document_type": "faq",
        "product_id": None,
        "product_name": None,
        "text": text,
        "metadata": {
            "source": "vietcombank_credit_faq",
            **faq["metadata"]
        }
    })


# 3. Loan FAQ
for faq in loan_faq:

    question = faq.get("question", "")
    answer = faq.get("answer", "")

    if question and answer:
        text = f"Question: {question}\nAnswer: {answer}"
    else:
        text = faq["full_text"]

    corpus.append({
        "doc_id": f"loan_faq_{faq['faq_id']}",
        "bank": faq["bank"],
        "product_type": "loan",
        "document_type": "faq",
        "product_id": faq["product_id"],
        "product_name": faq["product_name"],
        "text": text,
        "metadata": {
            "source": "vietcombank_loan_faq",
            **faq["metadata"]
        }
    })


# 4. Loan products
for loan in loans:

    text = f"Sản phẩm: {loan['name']}.\n{loan['full_text']}"

    corpus.append({
        "doc_id": f"loan_product_{loan['product_id']}",
        "bank": loan["bank"],
        "product_type": "loan",
        "document_type": "product",
        "product_id": loan["product_id"],
        "product_name": loan["name"],
        "text": text,
        "metadata": {
            "source": "vietcombank_loans",
            **loan["structured_features"],
            "url": loan["url"]
        }
    })


# Save corpus
with open("vietcombank_corpus.json", "w", encoding="utf-8") as f:
    json.dump(corpus, f, ensure_ascii=False, indent=2)

print("Total documents:", len(corpus))