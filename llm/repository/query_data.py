from pydantic import BaseModel, Field


class QueryData(BaseModel):
    title: str | None = Field(description='Predicted title with SLM')
    subtitle: str | None = Field(description='Predicted subtitle with SLM')
    query: str = Field(description='Query by user')
    embedding: list[float] = Field(description='Embedded query')
