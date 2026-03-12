import streamlit as st
import requests

API_URL = "http://localhost:8000/chat"

st.title("🏦 Banking AI Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

# hiển thị chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# user input
prompt = st.chat_input("Nhập câu hỏi của bạn...")

if prompt:

    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.write(prompt)

    payload = {
        "messages": st.session_state.messages
    }

    response = requests.post(API_URL, json=payload)

    answer = response.json()["answer"]

    with st.chat_message("assistant"):
        st.write(answer)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )