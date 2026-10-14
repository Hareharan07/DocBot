from fastapi import APIRouter, Depends

from ..errors import ApiError
from ..schemas import ChatRequest, ChatResponse
from ..security import get_container, get_owner_id
from ..services.chat import answer_question

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, owner_id: str = Depends(get_owner_id), container=Depends(get_container)):
    if container.llm is None:
        raise ApiError(503, "llm_not_configured",
                       "GROQ_API_KEY is not set. Add it to backend/.env and restart the server.")
    container.limiter.check(owner_id, "chat", container.settings.chat_rate_per_min)

    doc = container.db.get_document(req.doc_id, owner_id)  # owner-scoped: other users' docs look like 404
    if not doc:
        raise ApiError(404, "not_found", "Document not found.")
    if doc.status != "ready":
        raise ApiError(409, "not_ready", "This document isn't ready yet." if doc.status == "processing"
                       else "This document failed to process. Delete it and upload it again.")

    return answer_question(container, doc, req.question, [m.model_dump() for m in req.history])
