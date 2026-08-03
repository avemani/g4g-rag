import json
import asyncpg
from typing import List
from pydantic import TypeAdapter
from abc import ABC, abstractmethod
from pgvector.asyncpg import register_vector
from llm.repository.query_data import QueryData
from llm.repository.rag_data import RAGData



class BasePostgresConnector(ABC):
    @abstractmethod
    async def init_connection(self):
        raise NotImplementedError
    
    @abstractmethod
    async def save_history(self):
        raise NotImplementedError

    @abstractmethod
    async def get_history(self):
        raise NotImplementedError
    
    @abstractmethod
    async def get_data(self):
        raise NotImplementedError

    @abstractmethod
    async def close_connection(self):
        raise NotImplementedError
    


class PostgresConnector(BasePostgresConnector):
    def __init__(self, schema_name: str = 'vectors', table_name: str = 'geek_rag_1024'):
        self.schema_name = schema_name
        self.table_name = table_name
        self.initiated = False
        self.pool = None
        self.rag_adapter = TypeAdapter(List[RAGData])
        

    async def init_connection(self, user: str, password: str, host='postgres', port: int = 5432, database: str = 'geekdb'):
        async def init_pgvector(conn):
            await register_vector(conn)

        self.pool = await asyncpg.create_pool(
            user=user,
            password=password,
            database=database,
            port=port,
            host=host,
            min_size=5,
            max_size=20,
            setup=init_pgvector
        )

        self.initiated = True


    async def save_history(self, user_id: int, text: str, message_type: int):
        query = f"""
            INSERT INTO webapp.chat_history
            (user_id, text_message, message_type)
            values
            ($1, $2, $3)
        """

        turple_data = (user_id, text, message_type)

        async with self.pool.acquire() as conn:
            await conn.execute(query, *turple_data)


    async def get_history(self, user_id: int) -> list[dict]:
        query = f"""
            SELECT json_agg(row_to_json(t))
            FROM (
                SELECT id, user_id, text_message, message_type
                FROM webapp.chat_history
                WHERE user_id = $1
            ) t
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetchval(query, user_id)

        if not rows:
            return []
        
        json_data = json.loads(rows)

        return json_data



    async def get_data(self, data: QueryData, k: int = 60, limit: int = 50, use_meta: bool = True, use_kword: bool = True) -> list[RAGData]:
        if self.initiated:
            full_table_name = f'"{self.schema_name.replace('"', '""')}"."{self.table_name.replace('"', '""')}"'
            
            args = []
            
            def add_arg(value):
                args.append(value)
                return f"${len(args)}"
                
            if use_meta:
                title_idx = add_arg(data.title)
                subtitle_idx = add_arg(data.subtitle)
                filtered_docs_cte = f"""
                filtered_docs AS (
                    SELECT id, embedding, fts_tokens
                    FROM {full_table_name}
                    WHERE similarity(title, {title_idx}) > 0.15 
                    OR similarity(subtitle, {subtitle_idx}) > 0.15
                ),"""
            else:
                filtered_docs_cte = f"""
                filtered_docs AS (
                    SELECT id, embedding, fts_tokens
                    FROM {full_table_name}
                ),"""

            # 2. Формируем vector_search
            embedding_idx = add_arg(data.embedding)
            limit_idx = add_arg(limit)
            
            vector_search_cte = f"""
                vector_search AS (
                    SELECT id, RANK() OVER (ORDER BY embedding <=> {embedding_idx}::vector) AS rank
                    FROM filtered_docs
                    ORDER BY embedding <=> {embedding_idx}::vector
                    LIMIT {limit_idx}
                )"""

            k_idx = add_arg(k)
            
            if use_kword:
                query_idx = add_arg(data.query)
                keyword_and_rrf_ctes = f"""
                , keyword_search AS (
                    SELECT id, RANK() OVER (ORDER BY ts_rank(fts_tokens, websearch_to_tsquery('english', {query_idx})) DESC) AS rank
                    FROM filtered_docs
                    WHERE fts_tokens @@ websearch_to_tsquery('english', {query_idx})
                    ORDER BY ts_rank(fts_tokens, websearch_to_tsquery('english', {query_idx})) DESC
                    LIMIT {limit_idx}
                ),
                rrf_calc AS (
                    SELECT
                        COALESCE(v.id, ks.id) AS document_id,
                        COALESCE(1.0 / ({k_idx} + v.rank), 0.0) + COALESCE(1.0 / ({k_idx} + ks.rank), 0.0) AS rrf_score
                    FROM vector_search v
                    FULL OUTER JOIN keyword_search ks ON v.id = ks.id
                )"""
            else:
                keyword_and_rrf_ctes = f"""
                , rrf_calc AS (
                    SELECT
                        v.id AS document_id,
                        1.0 / ({k_idx} + v.rank) AS rrf_score
                    FROM vector_search v
                )"""

            # Собираем итоговый запрос
            query = f"""
                WITH {filtered_docs_cte}
                {vector_search_cte}
                {keyword_and_rrf_ctes}
                SELECT json_agg(row_to_json(t))
                FROM (
                    SELECT d.id, d.url, d.title, d.subtitle, d.text_data, r.rrf_score
                    FROM rrf_calc r
                    JOIN {full_table_name} d ON r.document_id = d.id
                    ORDER BY r.rrf_score DESC
                    LIMIT {limit_idx}
                ) t;
            """

            async with self.pool.acquire() as conn:
                rows = await conn.fetchval(query, *args)
            
            if rows is None:
                return []

            results = self.rag_adapter.validate_json(rows)
            return results
            
        else:
            print('Troubleshooting connection to the DB.')
            return None


    async def close_connection(self):
        if self.initiated:
            self.initiated = False
            await self.pool.close()
            self.pool = None
        else:
            print('Connection not initialized yet. Call PostgresConnector.init_connection before proceeding.')