from abc import ABC, abstractmethod
from typing import List

from ..models import RetrievedDocument


class BaseRetriever(ABC):

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int =15
    ) -> List[RetrievedDocument]:
        """
        Retrieve relevant information for a query.
        """
        raise NotImplementedError