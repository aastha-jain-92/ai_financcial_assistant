from typing import List

from .base import BaseRetriever
from ..models import RetrievedDocument


class ResearchRetriever(BaseRetriever):

    async def retrieve(
        self,
        query: str,
        top_k: int = 15
    ) -> List[RetrievedDocument]:

        # TODO:
        # Search research reports / analyst reports / stored documents.

        return []