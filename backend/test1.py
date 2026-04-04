import requests
import threading

URL = "https://banking-chatbot-1-081l.onrender.com/chat"

QUESTION = "Lợi ích của thẻ Vietcombank Cashplus Platinum American Express® là gì?"

def call(i):
    with requests.post(
        URL,
        json={
            "messages":[
                {"role":"user","content": QUESTION}
            ]
        },
        stream=True
    ) as r:

        print(f"\n---- user {i} ----")

        buffer = ""

        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                text = chunk.decode("utf-8")
                buffer += text

        print(f"\nUSER {i} RESULT:\n{buffer}")


threads = []

for i in range(40):   # test 3 user concurrent
    t = threading.Thread(target=call, args=(i,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()