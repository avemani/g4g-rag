import time
import streamlit as st
import requests


API_HISTORY_URL = 'http://localhost:8000/api/v1/chat/history'
API_CHAT_URL = 'http://localhost:8000/api/v1/chat/'


def fetch_chat_history(user_id: int):
    placeholder = st.empty()
    
    try:
        while True:
            try:
                response = requests.get(f'{API_HISTORY_URL}?user_id={user_id}')
                placeholder.empty()
                break
            except requests.exceptions.ConnectionError:
                with placeholder.container():
                    st.info('Server is loading...')

                time.sleep(2)

        response.raise_for_status()

        raw_history = response.json() 
        formatted_history = []

        if isinstance(raw_history, list):
            for item in raw_history:
                role = 'user' if item['message_type'] == 0 else 'assistant'
                
                formatted_history.append({
                    'role': role,
                    'content': item['text_message']
                })
            
        return formatted_history
        
    except requests.exceptions.RequestException as e:
        st.error(f'Error in GET request: {e}')
        return []


def ask_question(user_id: int, query: str):
    with st.chat_message('assistant'):
        with st.spinner('Generatig answer...'):
            payload = {
                'user_id': user_id,
                'message': query,
            }

            try:
                response = requests.post(
                    url=API_CHAT_URL,
                    json=payload
                )
                response.raise_for_status()

                answer = response.json()['reply']

                st.markdown(answer)
                st.session_state.messages.append({'role': 'assistant', 'content': answer})
            except requests.exceptions.RequestException as e:
                st.error(f'Server error: {e}')