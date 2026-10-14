import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile

from ..errors import ApiError
from ..schemas import DocumentOut
from ..security import get_container, get_owner_id
from ..services.extractor import ExtractionError, safe_display_name, validate_upload
from ..services.ingest import ingest_document

router = APIRouter(prefix="/documents")


@router.post("", status_code=202, response_model=DocumentOut)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    owner_id: str = Depends(get_owner_id),
    container=Depends(get_container),
):
    s = container.settings
    container.limiter.check(owner_id, "upload", s.upload_rate_per_min)

    content = await file.read(s.max_upload_bytes + 1)
    if len(content) > s.max_upload_bytes:
        raise ApiError(413, "file_too_large", f"File is larger than {s.max_upload_mb} MB.")

    filename = safe_display_name(file.filename)
    try:
        ext = validate_upload(filename, content)
    except ExtractionError as exc:
        raise ApiError(400, "invalid_file", str(exc)) from exc

    digest = hashlib.sha256(content).hexdigest()
    existing = container.db.find_by_hash(owner_id, digest)
    if existing:
        if existing.status == "failed":
            container.db.delete_document(existing.id, owner_id)  # allow a clean retry
        else:
            raise ApiError(
                409, "duplicate", f"\u201c{existing.filename}\u201d has already been uploaded.",
                {"document": DocumentOut.from_doc(existing).model_dump()},
            )

    doc = container.db.create_document(
        owner_id=owner_id, filename=filename, file_type=ext.lstrip("."),
        size_bytes=len(content), sha256=digest,
    )
    # Stored under a server-generated name: the user's filename never touches the filesystem.
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    raw_path = s.upload_dir / f"{doc.id}{ext}"
    raw_path.write_bytes(content)

    background.add_task(
        ingest_document, container, doc_id=doc.id, owner_id=owner_id,
        filename=filename, ext=ext, raw_path=raw_path,
    )
    return DocumentOut.from_doc(doc)


@router.get("", response_model=list[DocumentOut])
def list_documents(owner_id: str = Depends(get_owner_id), container=Depends(get_container)):
    return [DocumentOut.from_doc(d) for d in container.db.list_documents(owner_id)]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, owner_id: str = Depends(get_owner_id), container=Depends(get_container)):
    doc = container.db.get_document(doc_id, owner_id)
    if not doc:
        raise ApiError(404, "not_found", "Document not found.")
    return DocumentOut.from_doc(doc)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, owner_id: str = Depends(get_owner_id), container=Depends(get_container)):
    doc = container.db.get_document(doc_id, owner_id)
    if not doc:
        raise ApiError(404, "not_found", "Document not found.")
    container.store.delete_document(doc.id)      # vectors + text + metadata
    container.db.delete_document(doc.id, owner_id)
    for leftover in container.settings.upload_dir.glob(f"{doc.id}.*"):
        leftover.unlink(missing_ok=True)
    return Response(status_code=204)
