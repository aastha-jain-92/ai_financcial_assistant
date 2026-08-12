
from typing import List

from .models import RAGResult, RetrievedDocument

from .retrievers.base import BaseRetriever
from .retrievers.document_retriever import DocumentRetriever
from .retrievers.news_retriever import NewsRetriever
from .retrievers.research_retriever import ResearchRetriever

class RAGService:

    def __init__(
        self,
        document_retriever: BaseRetriever | None = None,
        news_retriever: BaseRetriever | None = None,
        research_retriever: BaseRetriever | None = None,
    ):

        self.document_retriever = (
            document_retriever
            or DocumentRetriever()
        )

        self.news_retriever = (
            news_retriever
            or NewsRetriever()
        )

        self.research_retriever = (
            research_retriever
            or ResearchRetriever()
        )


    async def retrieve(
        self,
        query: str,
        sources: List[str] | None = None,
        top_k: int = 5,
    ) -> RAGResult:

        if not sources:
            sources = [
                "document",
                "news",
                "research",
                "portfolio",
                "transaction",
            ]

        documents: List[RetrievedDocument] = []

        if "document" in sources:
            documents.extend(
                await self.document_retriever.retrieve(
                    query,
                    top_k
                )
            )

        if "news" in sources:
            documents.extend(
                await self.news_retriever.retrieve(
                    query,
                    top_k
                )
            )

        if "research" in sources:
            documents.extend(
                await self.research_retriever.retrieve(
                    query,
                    top_k
                )
            )

        context = self._build_context(documents)

        return RAGResult(
            context=context,
            documents=documents,
            sources=sources,
        )

    def _build_context(
        self,
        documents: List[RetrievedDocument]
    ) -> str:

        if not documents:
            return "No relevant information was retrieved."

        context_parts = []

        for index, document in enumerate(documents, start=1):

            context_parts.append(
                f"""
SOURCE {index}
TYPE: {document.source}

{document.content}
""".strip()
            )

        return "\n\n---\n\n".join(context_parts)