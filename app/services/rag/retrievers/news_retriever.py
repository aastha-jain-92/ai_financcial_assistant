from typing import List

from .base import BaseRetriever
from ..models import RetrievedDocument


class NewsRetriever(BaseRetriever):

    async def retrieve(
        self,
        query: str,
        top_k: int = 15
    ) -> List[RetrievedDocument]:

        # TODO:
        # Connect this to your news database/API/vector store.

        return []