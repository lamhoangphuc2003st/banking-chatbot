def build_context(docs):

    blocks = []

    for d in docs:

        block = f"""
Sản phẩm: {d.get("product_name","")}

Thông tin:
{d.get("text","")}
"""

        blocks.append(block)

    return "\n\n".join(blocks)