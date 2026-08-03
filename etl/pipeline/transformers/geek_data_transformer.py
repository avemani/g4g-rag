import numpy as np
import pandas as pd
from typing import List
from pydantic import TypeAdapter
from abc import ABC, abstractmethod
from pipeline.repository.geek_data import GeekData
from pipeline.transformers.token_transformer import TokenTransformator
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_classic.storage import LocalFileStore



class BaseGeekTransformer(ABC):
    @abstractmethod
    def transoform(self, documents: list[dict]) -> list[GeekData]:
        raise NotImplementedError
    

class GeekTransformer(BaseGeekTransformer):
    def __init__(self, tokenizer, batch_size, chunk_size, chunk_overlap, embedding_model):
        self.type_adapter = TypeAdapter(List[GeekData])
        self.batch_size = batch_size
        self.tokenizer = TokenTransformator(tokenizer)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self.tokenizer.length_function,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self.embeddings_model = OllamaEmbeddings(base_url='http://ollama-ai:11434', model=embedding_model)
        self.store = LocalFileStore("./.embed_cache/")
        self.cached_embedder = CacheBackedEmbeddings.from_bytes_store(
            underlying_embeddings=self.embeddings_model,
            document_embedding_cache=self.store,
            namespace=self.embeddings_model.model,
            key_encoder='sha256'
        )
   

    def transoform(self, documents: list[dict]) -> list[GeekData]:
        columns = ['source', 'order', 'type', 'name', 'class', 'line_start', 'line_end', 'sign_start', 'sign_end', 'is_subtitle', 'marker', 'breaker', 'text']
        
        df = pd.DataFrame(documents).sort_values(by=['source', 'order'], ignore_index=True)
        df = df.drop_duplicates(subset=['source', 'order', 'text'], keep='last')
        
        for column in columns:
            if column not in df.columns:
                df[column] = None
        
        df.loc[df['type'] == 'h1', 'title'] = df['text'].str.strip()
        df['title'] = df['title'].ffill()

        df['line_end'] = np.where(
            (df['line_start'].shift(-1) == True) & (df['line_end'].isnull()) & (df['breaker'].isnull()),
            True,
            df['line_end']
        )

        df.loc[df['breaker'] == True, 'text'] = '\n'
        df.loc[df['marker'] == True, 'text'] = '\t• ' + df['text']
        df.loc[df['sign_start'] == 'sup', 'text'] = '^{' + df['text']
        df.loc[df['sign_start'] == 'sub', 'text'] = '_{' + df['text']
        df.loc[df['sign_end'] == True, 'text'] = df['text'] + '}'
        df.loc[df['line_end'] == True, 'text'] = df['text'] + '\n'

        df.loc[df['is_subtitle'] == True, 'subtitle'] = df['text'].str.strip()
        df['subtitle'] = df['subtitle'].ffill()

        df = df.groupby(['source', 'title', 'subtitle'], as_index=False, sort=False).agg(
            {
                'text': lambda x: ''.join(x.astype(str)),
                'order': 'max'
            }
        )

        df = df.sort_values(by=['source', 'order'], ignore_index=True).reset_index(drop=True)
        df['main_order'] = df.groupby('source').cumcount() + 1

        df['chunks'] = df['text'].apply(self.text_splitter.split_text)
        df = df.explode('chunks')
        df['order'] = df.groupby(['source', 'subtitle']).cumcount() + 1
        df = df.drop(['text'], axis=1).reset_index(drop=True)
        
        data = []

        for i in range(0, len(df), self.batch_size):
            batch = df.iloc[i : i + self.batch_size].copy()
            batch['chunks'] = batch['chunks'].fillna('').astype(str)
            chunks_list = batch['chunks'].tolist()
            embeddings = self.cached_embedder.embed_documents(chunks_list)

            batch['embedding'] = list(embeddings)

            batch = batch.where(batch.notnull(), None)
            batch_dicts = batch.to_dict(orient='records')

            validated_records = self.type_adapter.validate_python(batch_dicts)
            data.extend(validated_records)

        return data