"""Sidecar domain models — re-exported from domain submodules."""
from .activity import ActivityEntry
from .fix import FixResult, LLMFixResponse
from .init import (
    DirRole,
    InitResult,
    LLMDirSummary,
    LLMFileSelectResponse,
    LLMInitFile,
    LLMInitResponse,
    LLMTreeChunkResponse,
)
from .review import (
    LLMReviewItem,
    LLMReviewResponse,
    ReviewCategory,
    ReviewItem,
    ReviewResult,
    ReviewSeverity,
)
from .scan import DocFile, DocScanResult
from .status import SidecarStatus

__all__ = [
    "ActivityEntry",
    "DirRole",
    "DocFile",
    "DocScanResult",
    "FixResult",
    "InitResult",
    "LLMDirSummary",
    "LLMFileSelectResponse",
    "LLMFixResponse",
    "LLMInitFile",
    "LLMInitResponse",
    "LLMReviewItem",
    "LLMReviewResponse",
    "LLMTreeChunkResponse",
    "ReviewCategory",
    "ReviewItem",
    "ReviewResult",
    "ReviewSeverity",
    "SidecarStatus",
]
