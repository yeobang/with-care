import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.deps import get_current_user, get_db
from app.domain.crew_service import _require_member
from app.domain.models import CareSession, SessionPhoto, User
from app.infra import storage

router = APIRouter(tags=["photos"])

ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_BYTES = 10 * 1024 * 1024


@router.post("/sessions/{session_id}/photos")
async def upload_photo(
    session_id: str,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.get(CareSession, session_id)
    if session is None:
        raise HTTPException(status_code=404)
    _require_member(db, session.crew_id, user.id)  # I6
    ext = ALLOWED_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(status_code=422, detail="jpeg/png/webp만 허용")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="10MB 이하만 허용")

    path = f"{session.crew_id}/{session_id}/{uuid.uuid4()}.{ext}"
    storage.upload(path, content, file.content_type or "image/jpeg")
    photo = SessionPhoto(
        session_id=session_id, crew_id=session.crew_id, uploaded_by=user.id, storage_path=path
    )
    db.add(photo)
    db.flush()
    notifications.notify_photo(db, session, user.id)  # best-effort
    return {"id": photo.id}


@router.get("/sessions/{session_id}/photos")
def list_photos(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.get(CareSession, session_id)
    if session is None:
        raise HTTPException(status_code=404)
    _require_member(db, session.crew_id, user.id)  # I6: 멤버십 검증 후에만 시한부 서명 URL 발급
    rows = db.scalars(
        select(SessionPhoto).where(SessionPhoto.session_id == session_id)
    ).all()
    urls = storage.signed_urls([p.storage_path for p in rows])  # N+1 회피: 일괄 서명
    return [
        {
            "id": p.id,
            "uploaded_by": p.uploaded_by,
            "created_at": p.created_at.isoformat(),
            "url": urls.get(p.storage_path),
        }
        for p in rows
    ]
