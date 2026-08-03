from fastapi import Request
from llm.search_engine.chat_llm import ChatLLM


def get_chat_service(request: Request) -> ChatLLM:
    return request.app.state.chat_service