import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/process-ticket"

st.title(" AI IT Support Assistant")

#  Session state
if "ticket" not in st.session_state:
    st.session_state.ticket = ""

if "step" not in st.session_state:
    st.session_state.step = 0

if "questions" not in st.session_state:
    st.session_state.questions = []

if "answers" not in st.session_state:
    st.session_state.answers = {}


#  Input box
user_input = st.text_input("Enter your issue or answer:")

#  Submit initial ticket
if st.button("Submit"):

    if st.session_state.step == 0:
        st.session_state.ticket = user_input

    else:
        # Add answers to ticket
        for q, ans in st.session_state.answers.items():
            st.session_state.ticket += f" {q}: {ans}"

    response = requests.post(API_URL, json={
        "ticket": st.session_state.ticket,
        "step": st.session_state.step
    })

    data = response.json()

    # 🔍 If more info needed
    if data["status"] == "need_info":
        st.session_state.questions = data["questions"]
        st.session_state.step += 1

    else:
        st.success(" Solution:")
        st.text_area("", data["result"], height=300)


# ❓ Show questions with input boxes
if st.session_state.questions:
    st.subheader("I need more info:")

    st.session_state.answers = {}

    for q in st.session_state.questions:
        ans = st.text_input(q, key=q)
        st.session_state.answers[q] = ans