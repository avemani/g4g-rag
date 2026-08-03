from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.config.settings import settings

from backend.api.routers import chat_router
from llm.search_engine.chat_llm import ChatLLM


@asynccontextmanager
async def lifespan(app: FastAPI):
    chat_service = ChatLLM(
        base_url=settings.litellm_url,
        api_key=settings.litellm_api_key,
        reranker_name=settings.reranker_name,
        caching=settings.caching,
    )

    await chat_service.init_connection(
        postgres_user=settings.db_user,
        postgres_password=settings.db_password
    )
    
    app.state.chat_service = chat_service

    yield
    
    await app.state.chat_service.close_connection()

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan
)

@app.get('/health', tags=['System'])
async def health_check():
    return {'status': 'ok', 'message': 'Uvicorn is running smoothly!'}


app.include_router(chat_router.router, prefix='/api/v1')