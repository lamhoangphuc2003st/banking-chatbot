def build_context(docs):
    if not docs:
        return "Không có dữ liệu."

    context_parts = []

    for i, d in enumerate(docs, 1):
        text = (d.get("text") or "").strip()
        product = d.get("product_name") or "Không rõ"

        part = f"""[Tài liệu {i}]
Sản phẩm: {product}
Nội dung: {text}
"""
        context_parts.append(part)

    return "\n\n".join(context_parts)