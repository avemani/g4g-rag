import asyncio
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI
from llm.repository.hypoth_metadata import HypotheticalMetadata


class BaseMetadataProcessor(ABC):
    @abstractmethod
    async def get_metadata(self):
        raise NotImplementedError


class MetadataProcessor(BaseMetadataProcessor):
    def __init__(self, base_url: str, api_key: str):
        self.slm = ChatOpenAI(
            model='mini-ollama',
            base_url=base_url,
            api_key=api_key,
            temperature=0.1
        )
        self.structured_slm = self.slm.with_structured_output(HypotheticalMetadata, method='json_schema')

    async def get_metadata(self, query: str) -> HypotheticalMetadata:
        prompt = (
            f"The user asked the question: '{query}'.\n"
            "Imagine that the answer is located within technical documentation.\n"
            "Come up with the most likely article title and subtitle "
            "where the answer would be found."
        )

        return await self.structured_slm.ainvoke(prompt)