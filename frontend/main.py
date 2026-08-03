import streamlit as st
import requests
from frontend.functions.chat import fetch_chat_history, ask_question


CURRENT_USER_ID = 1

st.title('AI Chat')


if 'messages' not in st.session_state:
    with st.spinner('Loading of chat history...'):
        st.session_state.messages = fetch_chat_history(user_id=CURRENT_USER_ID)

for msg in st.session_state.messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

if prompt := st.chat_input('Enter your query...'):
    st.session_state.messages.append({'role': 'user', 'content': prompt})
    with st.chat_message('user'):
        st.markdown(prompt)
        
    ask_question(user_id=CURRENT_USER_ID, query=prompt)