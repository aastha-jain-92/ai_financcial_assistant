from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievedDocument:
    """
    Represents one piece of information retrieved by a RAG source.
    """

    content: str
    source: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RAGResult:
    """
    Final result returned by the RAG service.
    """

    context: str
    documents: List[RetrievedDocument] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)