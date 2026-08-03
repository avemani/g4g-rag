from pydantic import BaseModel, Field


class RAGData(BaseModel):
    id: int = Field('Index in DB')
    url: str = Field('Source of data')
    title: str = Field(description='Predicted title with SLM')
    subtitle: str = Field(description='Predicted subtitle with SLM')
    text_data: str = Field(description='Data from RAG DB')
    rrf_score: float = Field(description='RRF score')
    rerank_score: float | None = Field(description='Score for reranking', default=None)