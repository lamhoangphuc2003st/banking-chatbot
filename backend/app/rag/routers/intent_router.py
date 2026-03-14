def classify_intent(query):

    q = query.lower()

    if "trả bao nhiêu" in q:
        return "loan_calculation"

    return "info_query"