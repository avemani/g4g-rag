from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int = Field(description='User ID', default=1)
    message: str = Field(min_length=1, description='User\'s request for LLM')

class ChatResponse(BaseModel):
    user_id: int = Field(description='User ID', default=1)
    reply: str = Field(description='LLM\'s response')

class ChatHistory(BaseModel):
    id: int = Field(description='ID of record')
    user_id: int = Field(description='User ID')
    message: str = Field(description='User\'s request for LLM/LLM\'s response')
    message_type: int = Field(description='0: request/1: response')
