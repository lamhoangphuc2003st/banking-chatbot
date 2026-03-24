def rrf_fusion(results_list, k=60):

    scores = {}

    for results in results_list:

        for rank, doc in enumerate(results):

            doc_id = doc["doc_id"]

            score = 1 / (k + rank + 1)

            if doc_id not in scores:
                scores[doc_id] = 0

            scores[doc_id] += score

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [doc_id for doc_id, _ in ranked]