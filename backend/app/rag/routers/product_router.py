def detect_product(query, products):

    q = query.lower()

    found = []

    for p in products:

        if p.lower() in q:
            found.append(p)

    return found or None