"""
Admin panel (REST) for your aiogram bot modules:
 - diagnostika (phrases + images)
 - hayvon_top (items with images+audios, grouped by category)
 - darslik (code+title+text+pdf)
 - bot users (upsert, block/unblock)
 - notify (broadcast/send text, audio/voice, video, photo to bot users)

Tech stack: FastAPI + SQLModel + SQLite.
Auth: X-API-Key header.
Static uploads: ./static/images, ./static/audios, ./static/pdfs, ./static/videos
Swagger UI: /docs (Authorize -> apiKey scheme).

Run:
  pip install fastapi uvicorn sqlmodel python-multipart httpx
  export ADMIN_API_KEY="changeme"            # or your own
  export TELEGRAM_BOT_TOKEN="12345:ABCDE"    # required for /notify/* endpoints
  uvicorn admin_app:app --reload --port 8099
"""

import os
import time
from typing import List, Optional, Dict, Any
from enum import Enum
from pathlib import Path
from datetime import datetime

import httpx
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File, Form,
    BackgroundTasks, Request
)
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from sqlmodel import SQLModel, Field, Session, create_engine, select

# ===================== Config =====================
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "changeme")

# Support both names to avoid breaking anything: prefer TELEGRAM_BOT_TOKEN, fallback botToken
PREF_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
ALT_BOT_TOKEN_ENV = "botToken"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "app.db"

IMG_DIR = BASE_DIR / "static" / "images"
AUD_DIR = BASE_DIR / "static" / "audios"
PDF_DIR = BASE_DIR / "static" / "pdfs"
VID_DIR = BASE_DIR / "static" / "videos"

# --- SEED DIAGNOSTIKA (10 ta) ---
SEED_DIAG = [
    ("Savat Asal Gilos", "/static/images/savat.png", 1),
    ("Zina Uzum Xo'roz", "/static/images/zina.png", 2),
    ("Shaftoli Qoshiq Quyosh", "/static/images/shaftoli.png", 3),
    ("Choynak Arg'imchoq uch", "/static/images/choynak.png", 4),
    ("Jo'ja Zanjir Toj", "/static/images/joja.png", 5),
    ("Likop Bulut Stol", "/static/images/likopcha.png", 6),
    ("Ruchka Arra Bir", "/static/images/ruchka.png", 7),
    ("Kitob Ukki Chelak", "/static/images/kitob.png", 8),
    ("Gilos Sigir Barg", "/static/images/gilos.png", 9),
    ("Qovun Baqlajon Tovuq", "/static/images/qovun.png", 10),
]

for p in (IMG_DIR, AUD_DIR, PDF_DIR, VID_DIR, DB_PATH.parent):
    p.mkdir(parents=True, exist_ok=True)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Depends(api_key_header)):
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ===================== Models =====================
class HayGroup(str, Enum):
    animal = "animal"
    action = "action"
    transport = "transport"
    nature = "nature"
    misc = "misc"


class DiagnostikaItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phrase: str
    image_path: str
    enabled: bool = True
    sort_order: int = 0


class HayvonItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str  # unique-like (validated on create/update)
    title: str
    group: HayGroup = Field(default=HayGroup.animal)
    image_path: str
    audio_path: str
    enabled: bool = True
    sort_order: int = 0


class Darslik(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)   # unique-like (validated)
    title: str
    text: str = ""
    pdf_path: str = ""              # /static/pdfs/...
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserRole(str, Enum):
    admin = "admin"
    teacher = "teacher"
    user = "user"


class BotUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tg_id: int = Field(index=True)  # unique-like (validated)
    username: Optional[str] = ""
    full_name: Optional[str] = ""
    role: UserRole = Field(default=UserRole.user)
    is_blocked: bool = False
    notes: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ===================== DB =====================
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


# ===================== App =====================
app = FastAPI(title="Bot Admin API", version="1.3.0")

# CORS (front-end uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # istasangiz aniq domenlarga toraytirishingiz mumkin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
def on_start():
    init_db()
    # Seed diagnostika if empty
    with Session(engine) as s:
        count = len(s.exec(select(DiagnostikaItem)).all())
        if count == 0:
            items = []
            for phrase, img, order in SEED_DIAG:
                items.append(DiagnostikaItem(
                    phrase=phrase, image_path=img, enabled=True, sort_order=order
                ))
            s.add_all(items)
            s.commit()


# Swagger'da apiKey ko'rsatish
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Admin API for bot",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# ===================== Uploads =====================
@app.post("/upload/image", dependencies=[Depends(require_api_key)])
def upload_image(file: UploadFile = File(...)):
    fname = file.filename or "image.bin"
    dest = IMG_DIR / fname
    i = 1
    while dest.exists():
        stem, suf = Path(fname).stem, Path(fname).suffix
        dest = IMG_DIR / f"{stem}_{i}{suf}"
        i += 1
    with dest.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/static/images/{dest.name}", "path": str(dest)}


@app.post("/upload/audio", dependencies=[Depends(require_api_key)])
def upload_audio(file: UploadFile = File(...)):
    fname = file.filename or "audio.bin"
    dest = AUD_DIR / fname
    i = 1
    while dest.exists():
        stem, suf = Path(fname).stem, Path(fname).suffix
        dest = AUD_DIR / f"{stem}_{i}{suf}"
        i += 1
    with dest.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/static/audios/{dest.name}", "path": str(dest)}


@app.post("/upload/pdf", dependencies=[Depends(require_api_key)])
def upload_pdf(file: UploadFile = File(...)):
    fname = file.filename or "doc.pdf"
    dest = PDF_DIR / fname
    i = 1
    while dest.exists():
        stem, suf = Path(fname).stem, Path(fname).suffix
        dest = PDF_DIR / f"{stem}_{i}{suf}"
        i += 1
    with dest.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/static/pdfs/{dest.name}", "path": str(dest)}


@app.post("/upload/video", dependencies=[Depends(require_api_key)])
def upload_video(file: UploadFile = File(...)):
    fname = file.filename or "video.bin"
    dest = VID_DIR / fname
    i = 1
    while dest.exists():
        stem, suf = Path(fname).stem, Path(fname).suffix
        dest = VID_DIR / f"{stem}_{i}{suf}"
        i += 1
    with dest.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/static/videos/{dest.name}", "path": str(dest)}


# ===================== Diagnostika CRUD =====================
@app.get("/diagnostika", response_model=List[DiagnostikaItem])
def list_diag(enabled: Optional[bool] = None):
    with Session(engine) as s:
        query = select(DiagnostikaItem).order_by(DiagnostikaItem.sort_order)
        if enabled is not None:
            query = query.where(DiagnostikaItem.enabled == enabled)
        return s.exec(query).all()


@app.post("/diagnostika", response_model=DiagnostikaItem, dependencies=[Depends(require_api_key)])
def create_diag(item: DiagnostikaItem):
    with Session(engine) as s:
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.put("/diagnostika/{item_id}", response_model=DiagnostikaItem, dependencies=[Depends(require_api_key)])
def update_diag(item_id: int, data: DiagnostikaItem):
    with Session(engine) as s:
        obj = s.get(DiagnostikaItem, item_id)
        if not obj:
            raise HTTPException(404)
        for f in ["phrase", "image_path", "enabled", "sort_order"]:
            setattr(obj, f, getattr(data, f))
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


@app.delete("/diagnostika/{item_id}", dependencies=[Depends(require_api_key)])
def delete_diag(item_id: int):
    with Session(engine) as s:
        obj = s.get(DiagnostikaItem, item_id)
        if not obj:
            raise HTTPException(404)
        s.delete(obj)
        s.commit()
        return {"ok": True}


# ===================== Hayvon_top CRUD =====================
@app.get("/hayvon", response_model=List[HayvonItem])
def list_hayvon(enabled: Optional[bool] = None, group: Optional[HayGroup] = None):
    with Session(engine) as s:
        query = select(HayvonItem).order_by(HayvonItem.group, HayvonItem.sort_order)
        if enabled is not None:
            query = query.where(HayvonItem.enabled == enabled)
        if group is not None:
            query = query.where(HayvonItem.group == group)
        return s.exec(query).all()


@app.post("/hayvon", response_model=HayvonItem, dependencies=[Depends(require_api_key)])
def create_hayvon(item: HayvonItem):
    with Session(engine) as s:
        exists = s.exec(select(HayvonItem).where(HayvonItem.key == item.key)).first()
        if exists:
            raise HTTPException(409, detail="key already exists")
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.put("/hayvon/{item_id}", response_model=HayvonItem, dependencies=[Depends(require_api_key)])
def update_hayvon(item_id: int, data: HayvonItem):
    with Session(engine) as s:
        obj = s.get(HayvonItem, item_id)
        if not obj:
            raise HTTPException(404)
        if data.key != obj.key:
            dupe = s.exec(select(HayvonItem).where(HayvonItem.key == data.key)).first()
            if dupe:
                raise HTTPException(409, detail="key already exists")
        for f in ["key", "title", "group", "image_path", "audio_path", "enabled", "sort_order"]:
            setattr(obj, f, getattr(data, f))
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


@app.delete("/hayvon/{item_id}", dependencies=[Depends(require_api_key)])
def delete_hayvon(item_id: int):
    with Session(engine) as s:
        obj = s.get(HayvonItem, item_id)
        if not obj:
            raise HTTPException(404)
        s.delete(obj)
        s.commit()
        return {"ok": True}


# ===================== Darslik CRUD & Export =====================
@app.get("/darslik", response_model=List[Darslik])
def list_darslik(
    code: Optional[str] = None,
    title: Optional[str] = None,
    enabled: Optional[bool] = None,
):
    with Session(engine) as s:
        q = select(Darslik).order_by(Darslik.created_at.desc())
        if enabled is not None:
            q = q.where(Darslik.enabled == enabled)
        if code:
            q = q.where(Darslik.code.contains(code))
        if title:
            q = q.where(Darslik.title.contains(title))
        return s.exec(q).all()


@app.post("/darslik", response_model=Darslik, dependencies=[Depends(require_api_key)])
def create_darslik(item: Darslik):
    with Session(engine) as s:
        exists = s.exec(select(Darslik).where(Darslik.code == item.code)).first()
        if exists:
            raise HTTPException(409, detail="code already exists")
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.put("/darslik/{item_id}", response_model=Darslik, dependencies=[Depends(require_api_key)])
def update_darslik(item_id: int, data: Darslik):
    with Session(engine) as s:
        obj = s.get(Darslik, item_id)
        if not obj:
            raise HTTPException(404)
        if data.code != obj.code:
            dupe = s.exec(select(Darslik).where(Darslik.code == data.code)).first()
            if dupe:
                raise HTTPException(409, detail="code already exists")
        for f in ["code", "title", "text", "pdf_path", "enabled"]:
            setattr(obj, f, getattr(data, f))
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


@app.delete("/darslik/{item_id}", dependencies=[Depends(require_api_key)])
def delete_darslik(item_id: int):
    with Session(engine) as s:
        obj = s.get(Darslik, item_id)
        if not obj:
            raise HTTPException(404)
        s.delete(obj)
        s.commit()
        return {"ok": True}


@app.get("/darslik/by-code/{code}", response_model=Darslik)
def get_darslik_by_code(code: str):
    with Session(engine) as s:
        obj = s.exec(select(Darslik).where(Darslik.code == code)).first()
        if not obj:
            raise HTTPException(404, detail="not found")
        return obj


# ===================== Users CRUD, Upsert & Block (restored) =====================
@app.get("/users", response_model=List[BotUser])
def list_users(
    blocked: Optional[bool] = None,
    username: Optional[str] = None,
    role: Optional[UserRole] = None,
):
    with Session(engine) as s:
        q = select(BotUser).order_by(BotUser.created_at.desc())
        if blocked is not None:
            q = q.where(BotUser.is_blocked == blocked)
        if username:
            q = q.where(BotUser.username.contains(username))
        if role is not None:
            q = q.where(BotUser.role == role)
        return s.exec(q).all()


@app.post("/users", response_model=BotUser, dependencies=[Depends(require_api_key)])
def create_user(item: BotUser):
    with Session(engine) as s:
        exists = s.exec(select(BotUser).where(BotUser.tg_id == item.tg_id)).first()
        if exists:
            raise HTTPException(409, detail="tg_id already exists")
        s.add(item)
        s.commit()
        s.refresh(item)
        return item


@app.put("/users/{user_id}", response_model=BotUser, dependencies=[Depends(require_api_key)])
def update_user(user_id: int, data: BotUser):
    with Session(engine) as s:
        obj = s.get(BotUser, user_id)
        if not obj:
            raise HTTPException(404)
        if data.tg_id != obj.tg_id:
            dupe = s.exec(select(BotUser).where(BotUser.tg_id == data.tg_id)).first()
            if dupe:
                raise HTTPException(409, detail="tg_id already exists")
        for f in ["tg_id", "username", "full_name", "role", "is_blocked", "notes"]:
            setattr(obj, f, getattr(data, f))
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


@app.delete("/users/{user_id}", dependencies=[Depends(require_api_key)])
def delete_user(user_id: int):
    with Session(engine) as s:
        obj = s.get(BotUser, user_id)
        if not obj:
            raise HTTPException(404)
        s.delete(obj)
        s.commit()
        return {"ok": True}


@app.post("/users/upsert", response_model=BotUser, dependencies=[Depends(require_api_key)])
def upsert_user(
    tg_id: int = Form(...),
    username: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    role: UserRole = Form(UserRole.user),
    notes: Optional[str] = Form(None),
):
    with Session(engine) as s:
        obj = s.exec(select(BotUser).where(BotUser.tg_id == tg_id)).first()
        if obj:
            obj.username = username or obj.username
            obj.full_name = full_name or obj.full_name
            obj.role = role or obj.role
            obj.notes = notes or obj.notes
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj
        new_u = BotUser(
            tg_id=tg_id,
            username=username or "",
            full_name=full_name or "",
            role=role,
            notes=notes or "",
        )
        s.add(new_u)
        s.commit()
        s.refresh(new_u)
        return new_u


@app.post("/users/{user_id}/block", response_model=BotUser, dependencies=[Depends(require_api_key)])
def block_user(user_id: int):
    with Session(engine) as s:
        obj = s.get(BotUser, user_id)
        if not obj:
            raise HTTPException(404)
        obj.is_blocked = True
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


@app.post("/users/{user_id}/unblock", response_model=BotUser, dependencies=[Depends(require_api_key)])
def unblock_user(user_id: int):
    with Session(engine) as s:
        obj = s.get(BotUser, user_id)
        if not obj:
            raise HTTPException(404)
        obj.is_blocked = False
        s.add(obj)
        s.commit()
        s.refresh(obj)
        return obj


# ===================== Exports for bot =====================
@app.get("/export/diagnostika")
def export_diag(enabled_only: bool = True):
    with Session(engine) as s:
        q = select(DiagnostikaItem).order_by(DiagnostikaItem.sort_order)
        if enabled_only:
            q = q.where(DiagnostikaItem.enabled == True)
        items = s.exec(q).all()
    return [
        {
            "phrase": i.phrase,
            "image_url": i.image_path if i.image_path.startswith("/static/") else f"/static/images/{Path(i.image_path).name}"
        }
        for i in items
    ]


@app.get("/export/hayvon")
def export_hayvon(enabled_only: bool = True, group: Optional[HayGroup] = None):
    with Session(engine) as s:
        q = select(HayvonItem).order_by(HayvonItem.group, HayvonItem.sort_order)
        if enabled_only:
            q = q.where(HayvonItem.enabled == True)
        if group is not None:
            q = q.where(HayvonItem.group == group)
        items = s.exec(q).all()
    return [
        {
            "key": i.key,
            "title": i.title,
            "group": i.group,
            "image_url": i.image_path if i.image_path.startswith("/static/") else f"/static/images/{Path(i.image_path).name}",
            "audio_url": i.audio_path if i.audio_path.startswith("/static/") else f"/static/audios/{Path(i.audio_path).name}",
        }
        for i in items
    ]


@app.get("/export/darslik/{code}")
def export_darslik(code: str):
    with Session(engine) as s:
        obj = s.exec(select(Darslik).where(Darslik.code == code, Darslik.enabled == True)).first()
        if not obj:
            raise HTTPException(404, detail="not found or disabled")
        pdf_url = obj.pdf_path if obj.pdf_path.startswith("/static/") else f"/static/pdfs/{Path(obj.pdf_path).name}"
        return {"code": obj.code, "title": obj.title, "text": obj.text, "pdf_url": pdf_url}


# ===================== Statistics =====================
@app.get("/stats")
def stats() -> Dict[str, Any]:
    """
    Returns aggregated counts and distributions for dashboard cards:
      - totals (diagnostika/hayvon/darslik/users)
      - enabled counts
      - hayvon by group distribution
      - users by role, blocked count
      - lessons enabled/disabled counts
    """
    with Session(engine) as s:
        # Diagnostika
        diag_total = s.exec(select(DiagnostikaItem)).all()
        diag_enabled = [d for d in diag_total if d.enabled]
        # Hayvon
        hay_total = s.exec(select(HayvonItem)).all()
        hay_enabled = [h for h in hay_total if h.enabled]
        by_group: Dict[str, int] = {}
        for g in HayGroup:
            by_group[g.value] = len([x for x in hay_total if x.group == g])
        # Darslik
        lessons = s.exec(select(Darslik)).all()
        lessons_enabled = [l for l in lessons if l.enabled]
        # Users
        users = s.exec(select(BotUser)).all()
        users_by_role: Dict[str, int] = {"admin": 0, "teacher": 0, "user": 0}
        blocked_count = 0
        for u in users:
            users_by_role[u.role.value] = users_by_role.get(u.role.value, 0) + 1
            if u.is_blocked:
                blocked_count += 1

        return {
            "totals": {
                "diagnostika": len(diag_total),
                "diagnostika_enabled": len(diag_enabled),
                "hayvon": len(hay_total),
                "hayvon_enabled": len(hay_enabled),
                "darslik": len(lessons),
                "darslik_enabled": len(lessons_enabled),
                "users": len(users),
                "users_blocked": blocked_count,
            },
            "hayvon_by_group": by_group,
            "users_by_role": users_by_role,
        }


@app.get("/")
def root():
    return {"name": "Bot Admin API", "ok": True}


# ===================== NOTIFY (send to bot users) =====================
def _ensure_bot_token() -> str:
    token = os.getenv(PREF_BOT_TOKEN_ENV, "").strip()
    if not token:
        token = os.getenv(ALT_BOT_TOKEN_ENV, "").strip()
    if not token:
        raise HTTPException(
            500,
            detail=f"{PREF_BOT_TOKEN_ENV} is not set (also checked {ALT_BOT_TOKEN_ENV})"
        )
    return token


def _tg_api_base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}/"


def _abs_url_from_req(req: Request, path_or_url: str) -> str:
    if not path_or_url:
        return path_or_url
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    scheme = req.headers.get("X-Forwarded-Proto") or req.url.scheme
    host = req.headers.get("X-Forwarded-Host") or req.headers.get("Host") or req.url.netloc
    return f"{scheme}://{host}{path_or_url}"


def _select_targets(
    tg_id: Optional[int],
    role: Optional[UserRole],
    include_blocked: bool,
    to_all: bool = False,
) -> List[int]:
    with Session(engine) as s:
        if not to_all and tg_id:
            u = s.exec(select(BotUser).where(BotUser.tg_id == tg_id)).first()
            if not u:
                raise HTTPException(404, detail="tg_id not found in users table")
            if u.is_blocked and not include_blocked:
                return []
            return [u.tg_id]

        q = select(BotUser)
        if not to_all and role:
            q = q.where(BotUser.role == role)

        users = s.exec(q).all()
        out = []
        for u in users:
            if not include_blocked and u.is_blocked:
                continue
            out.append(u.tg_id)
        return out


def _broadcast_sync(
    method: str,
    media_field: Optional[str],            # "audio" | "voice" | "video" | "photo" | None
    media_url: Optional[str],              # absolute url or None
    text_or_caption: Optional[str],
    parse_mode: Optional[str],
    disable_web_page_preview: Optional[bool],
    disable_notification: bool,
    targets: List[int],
):
    token = _ensure_bot_token()
    base = _tg_api_base(token)
    with httpx.Client(base_url=base, timeout=httpx.Timeout(30, connect=10)) as client:
        for chat_id in targets:
            data: Dict[str, Any] = {"chat_id": chat_id, "disable_notification": disable_notification}
            if method == "sendMessage":
                data["text"] = text_or_caption or ""
                if parse_mode:
                    data["parse_mode"] = parse_mode
                if disable_web_page_preview is not None:
                    data["disable_web_page_preview"] = disable_web_page_preview
            else:
                if media_field and media_url:
                    data[media_field] = media_url
                if text_or_caption:
                    data["caption"] = text_or_caption
                if parse_mode:
                    data["parse_mode"] = parse_mode

            try:
                resp = client.post(method, data=data)
                if resp.status_code != 200:
                    # You can log resp.text here if needed
                    pass
            except Exception:
                pass

            time.sleep(0.05)  # avoid flood

# ---- TEXT ----
@app.post("/notify/text", dependencies=[Depends(require_api_key)])
def notify_text(
    request: Request,
    background: BackgroundTasks,
    text: str = Form(...),
    tg_id: Optional[int] = Form(None),
    role: Optional[UserRole] = Form(None),
    include_blocked: bool = Form(False),
    parse_mode: Optional[str] = Form("HTML"),
    disable_web_page_preview: bool = Form(False),
    disable_notification: bool = Form(False),
    to_all: bool = Form(False),
):
    _ensure_bot_token()
    targets = _select_targets(
        tg_id=tg_id, role=role, include_blocked=include_blocked, to_all=to_all
    )
    if not targets:
        return {"scheduled": 0, "method": "sendMessage", "to_all": to_all}
    background.add_task(
        _broadcast_sync,
        "sendMessage",
        None, None,
        text,
        parse_mode,
        disable_web_page_preview,
        disable_notification,
        targets,
    )
    return {"scheduled": len(targets), "method": "sendMessage", "to_all": to_all}

# ---- AUDIO/VOICE ----
@app.post("/notify/audio", dependencies=[Depends(require_api_key)])
def notify_audio(
    request: Request,
    background: BackgroundTasks,
    media_url: str = Form(...),                 # /static/audios/xxx.mp3 yoki http(s) url
    caption: Optional[str] = Form(None),
    as_voice: bool = Form(False),               # True -> sendVoice, False -> sendAudio
    tg_id: Optional[int] = Form(None),
    role: Optional[UserRole] = Form(None),
    include_blocked: bool = Form(False),
    parse_mode: Optional[str] = Form("HTML"),
    disable_notification: bool = Form(False),
    to_all: bool = Form(False),
):
    _ensure_bot_token()
    absolute = _abs_url_from_req(request, media_url)
    method = "sendVoice" if as_voice else "sendAudio"
    field_name = "voice" if as_voice else "audio"
    targets = _select_targets(
        tg_id=tg_id, role=role, include_blocked=include_blocked, to_all=to_all
    )
    if not targets:
        return {"scheduled": 0, "method": method, "media": absolute, "to_all": to_all}
    background.add_task(
        _broadcast_sync,
        method,
        field_name,
        absolute,
        caption,
        parse_mode,
        None,
        disable_notification,
        targets,
    )
    return {"scheduled": len(targets), "method": method, "media": absolute, "to_all": to_all}

# ---- VIDEO ----
@app.post("/notify/video", dependencies=[Depends(require_api_key)])
def notify_video(
    request: Request,
    background: BackgroundTasks,
    media_url: str = Form(...),                # /static/videos/xxx.mp4 yoki http(s) url
    caption: Optional[str] = Form(None),
    tg_id: Optional[int] = Form(None),
    role: Optional[UserRole] = Form(None),
    include_blocked: bool = Form(False),
    parse_mode: Optional[str] = Form("HTML"),
    disable_notification: bool = Form(False),
    to_all: bool = Form(False),
):
    _ensure_bot_token()
    absolute = _abs_url_from_req(request, media_url)
    targets = _select_targets(
        tg_id=tg_id, role=role, include_blocked=include_blocked, to_all=to_all
    )
    if not targets:
        return {"scheduled": 0, "method": "sendVideo", "media": absolute, "to_all": to_all}
    background.add_task(
        _broadcast_sync,
        "sendVideo",
        "video",
        absolute,
        caption,
        parse_mode,
        None,
        disable_notification,
        targets,
    )
    return {"scheduled": len(targets), "method": "sendVideo", "media": absolute, "to_all": to_all}

# ---- PHOTO (NEW) ----
@app.post("/notify/photo", dependencies=[Depends(require_api_key)])
def notify_photo(
    request: Request,
    background: BackgroundTasks,
    media_url: str = Form(...),                # /static/images/xxx.png (or jpg/webp) yoki http(s) url
    caption: Optional[str] = Form(None),
    tg_id: Optional[int] = Form(None),
    role: Optional[UserRole] = Form(None),
    include_blocked: bool = Form(False),
    parse_mode: Optional[str] = Form("HTML"),
    disable_notification: bool = Form(False),
    to_all: bool = Form(False),
):
    """
    Broadcast a photo with optional caption.
    Use /upload/image first to get /static/images/... then pass as media_url here.
    """
    _ensure_bot_token()
    absolute = _abs_url_from_req(request, media_url)
    targets = _select_targets(
        tg_id=tg_id, role=role, include_blocked=include_blocked, to_all=to_all
    )
    if not targets:
        return {"scheduled": 0, "method": "sendPhoto", "media": absolute, "to_all": to_all}
    background.add_task(
        _broadcast_sync,
        "sendPhoto",
        "photo",
        absolute,
        caption,
        parse_mode,
        None,
        disable_notification,
        targets,
    )
    return {"scheduled": len(targets), "method": "sendPhoto", "media": absolute, "to_all": to_all}
