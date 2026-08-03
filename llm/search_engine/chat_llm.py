import re
import asyncio
from typing import List
from pydantic import TypeAdapter
from abc import ABC, abstractmethod
from os import path, listdir
from sentence_transformers import CrossEncoder
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from llm.repository.query_data import QueryData
from llm.repository.rag_data import RAGData
from llm.connections.postgres_connector import PostgresConnector
from llm.query_processing.metadata_processing import MetadataProcessor
from llm.query_processing.query_embedding import QueryEmbedder



class BaseChatLLM(ABC):
    @abstractmethod
    async def get_rag_data(self):
        raise NotImplementedError

    @abstractmethod
    async def init_connection(self):
        raise NotImplementedError

    @abstractmethod
    def litm_reorder(self):
        raise NotImplementedError

    @abstractmethod
    def rerank_data(self):
        raise NotImplementedError

    @abstractmethod
    async def generate_answer(self):
        raise NotImplementedError

    @abstractmethod
    async def save_history(self):
        raise NotImplementedError

    @abstractmethod
    async def get_history(self):
        raise NotImplementedError

    @abstractmethod
    async def close_connection(self):
        raise NotImplementedError


class ChatLLM(BaseChatLLM):
    def __init__(self, base_url: str, api_key: str, reranker_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2', caching: bool = True):
        self.db_connector = PostgresConnector()
        self.meta = MetadataProcessor(base_url=base_url, api_key=api_key)
        self.embedding = QueryEmbedder(base_url=base_url, api_key=api_key)
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model='local-ollama',
            temperature=0.0,
            extra_body={'caching': caching},
        )
        reranker_path = f'./llm/encoder/{re.sub(r'[./:]', '_', reranker_name)}'
        if path.exists(reranker_path) and listdir(reranker_path):
            self.reranker = CrossEncoder(reranker_path, local_files_only=True)
        else:
            self.reranker = CrossEncoder(reranker_name)
            self.reranker.save(reranker_path)
        self.adapter = TypeAdapter(List[RAGData])


    async def init_connection(self, postgres_user: str, postgres_password: str):
        if self.db_connector.initiated == False:
            await self.db_connector.init_connection(user=postgres_user, password=postgres_password)
        else:
            print('DB already connected')
    

    async def get_rag_data(self, query: str, use_meta: bool = True, use_kword: bool = True, k: int = 60, limit: int = 50) -> list[str]:
        if use_meta:
            slm_result = await self.meta.get_metadata(query=query)
            title = slm_result.title
            subtitle = slm_result.subtitle
        else:
            title = None
            subtitle = None

        embedding = await self.embedding.embed_query(query=query)

        query_data = QueryData(
            title=title,
            subtitle=subtitle,
            query=query,
            embedding=embedding
        )

        chunks = await self.db_connector.get_data(data=query_data, use_meta=use_meta, use_kword=use_kword, k=k, limit=limit)
        chunks = self.adapter.validate_python(chunks)

        return chunks


    def litm_reorder(self, chunks: list[RAGData]) -> list[str]:
        if not chunks:
            return []

        reordered = [None] * len(chunks)
        left, right = 0, len(chunks) - 1
        for i, chunk in enumerate(chunks):
            if i % 2 == 0:
                reordered[left] = chunk
                left += 1
            else:
                reordered[right] = chunk
                right -= 1

        return reordered


    def rerank_data(self, query: str, chunks: List[RAGData], use_rerank: bool = True, t: int = 5) -> list[str]:
        if use_rerank:
            pairs = [[query, f'{chunk.title}\n{chunk.subtitle}\n{chunk.text_data}'] for chunk in chunks]
            scores = self.reranker.predict(pairs)

            for i, chunk in enumerate(chunks):
                chunk.rerank_score = float(scores[i])

            optimal_chunks = sorted(chunks, key=lambda x: x.rerank_score, reverse=True)[:t]
        else:
            optimal_chunks = chunks[:t]

        optimal_chunks = self.litm_reorder(optimal_chunks)

        return optimal_chunks


    async def generate_answer(
        self,
        query: str, 
        use_meta: bool = True, 
        use_kword: bool = True,
        use_rerank: bool = True, 
        k: int = 60, 
        limit: int = 50,
        t: int = 5,
        eval: bool = False
    ) -> str | tuple[str, str]:
        chunks = await self.get_rag_data(query=query, use_meta=use_meta, use_kword=use_kword, k=k, limit=limit)
        optimal_chunks = self.rerank_data(query=query, chunks=chunks, use_rerank=use_rerank, t=t)

        context_parts = []
        for i, chunk in enumerate(optimal_chunks, 1):
            context_parts.append(f'--- SOURCE {i}: {chunk.url} ---\n{chunk.text_data}\n')
        
        context_string = '\n\n'.join(context_parts)
        
        system_prompt = (
            'You are an accurate and helpful AI assistant for the corporate knowledge base.\n'
            'Your task is to answer the user\'s question using ONLY the provided context.\n'
            'RULES:\n'
            '1. If the context does not contain enough information to answer, state honestly: "I could not find information on this topic in the knowledge base."\n'
            '2. Do not make up facts or use external knowledge.\n'
            '3. At the end of your response, briefly indicate the sources you relied on (e.g., "Source: https://example.com").'
        )
        
        user_prompt = f'CONTEXT:\n{context_string}\n\nUSER QUERY:\n{query}'
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)

            if eval:
                retrieved_contexts = []
                for chunk in optimal_chunks:
                    retrieved_contexts.append(chunk.text_data)
                    
                return response.content, retrieved_contexts
            else:
                return response.content
            
        except Exception as e:
            return f'Error occurred during answer generation: {e}'


    async def save_history(self, user_id: int, text: str, message_type: int):
        await self.db_connector.save_history(user_id=user_id, text=text, message_type=message_type)


    async def get_history(self, user_id: int) -> list[dict]:
        json_data = await self.db_connector.get_history(user_id=user_id)
        if json_data:
            sorted_data = sorted(json_data, key=lambda x: x['id'])
        else:
            return []

        return sorted_data


    async def close_connection(self):
        if self.db_connector.initiated == True:
            await self.db_connector.close_connection()
        else:
            print('DB already disconnected')