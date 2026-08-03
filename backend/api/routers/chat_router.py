from fastapi import APIRouter, Depends
from backend.repository.chat import ChatRequest, ChatResponse
from llm.search_engine.chat_llm import ChatLLM
from backend.api.dependencies import get_chat_service


router = APIRouter(prefix='/chat', tags=['AI Chat'])

@router.post('/', response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    service: ChatLLM = Depends(get_chat_service)
):
    await service.save_history(user_id=request.user_id, text=request.message, message_type=0)
    reply = await service.generate_answer(query=request.message, use_kword=False, use_meta=True, use_rerank=True, k=50, limit=30, t=3)
    await service.save_history(user_id=request.user_id, text=reply, message_type=1)
    
    return ChatResponse(reply=reply)


@router.get('/history')
async def get_history(
    user_id: int,
    service: ChatLLM = Depends(get_chat_service)
):
    history = await service.get_history(user_id)

    return history