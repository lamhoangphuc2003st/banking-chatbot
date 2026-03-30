def build_context(docs):
    if not docs:
        return "Không có dữ liệu."

    context_parts = []

    for d in docs:
        text = (d.get("text") or "").strip()
        if text:
            context_parts.append(text)

    return "\n\n".join(context_parts)