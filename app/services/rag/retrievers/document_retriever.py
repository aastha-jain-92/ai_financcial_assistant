from typing import List

from .base import BaseRetriever
from ..models import RetrievedDocument


class DocumentRetriever(BaseRetriever):

    async def retrieve(
        self,
        query: str,
        top_k: int = 15
    ) -> List[RetrievedDocument]:

        # TODO:
        # Replace this with vector database search later.

        return []