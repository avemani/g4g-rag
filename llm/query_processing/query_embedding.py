import asyncio
from abc import ABC, abstractmethod
from langchain_openai import OpenAIEmbeddings


class BaseQueryEmbedder(ABC):
    @abstractmethod
    async def embed_query(self):
        raise NotImplementedError


class QueryEmbedder(BaseQueryEmbedder):
    def __init__(self, base_url: str, api_key: str):
        self.embedder = OpenAIEmbeddings(
            model='ollama-embedding',
            openai_api_base=base_url,
            api_key=api_key,
            check_embedding_ctx_length=False
        )


    async def embed_query(self, query: str) -> list[float]:
        return await self.embedder.aembed_query(query)