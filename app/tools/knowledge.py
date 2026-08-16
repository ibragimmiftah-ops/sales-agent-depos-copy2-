"""search_knowledge_base tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, register_tool


class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(..., description="Search query")
    category: str | None = Field(None, description="Optional metadata category filter")
    top_k: int = Field(5, description="Number of results")


class SearchKnowledgeBaseOutput(BaseModel):
    results: list[dict[str, Any]]


class SearchKnowledgeBaseTool(Tool[SearchKnowledgeBaseInput]):
    name = "search_knowledge_base"
    description = "Search the company knowledge base for relevant information."
    input_schema = SearchKnowledgeBaseInput
    output_schema = SearchKnowledgeBaseOutput

    async def execute(self, context: ToolContext, arguments: SearchKnowledgeBaseInput) -> dict[str, Any]:
        results = await context.retriever.search(
            query=arguments.query,
            category=arguments.category,
            top_k=arguments.top_k,
        )
        return {"results": [dict(r) for r in results]}


register_tool(SearchKnowledgeBaseTool())
