from fastapi import APIRouter, Depends

from ..security import get_container

router = APIRouter()


@router.get("/health")
def health(container=Depends(get_container)):
    s = container.settings
    return {
        "status": "ok",
        "llm_configured": container.llm is not None,  # a boolean only - never the key itself
        "embedding_model": s.embedding_model,
        "limits": {"max_upload_mb": s.max_upload_mb, "allowed_types": [".pdf", ".docx", ".txt"]},
    }
