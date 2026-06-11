from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.admin import router as admin_router
from app.config import settings
from app.database import get_db
from app.models import Category, Demo

app = FastAPI(title="Demo 展示网站")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.include_router(admin_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/demos", StaticFiles(directory=settings.demos_dir), name="demos")
app.mount("/thumbnails", StaticFiles(directory=settings.thumbnails_dir), name="thumbnails")

templates = Jinja2Templates(directory="app/templates")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(
        select(Category).order_by(Category.sort_order, Category.id)
    ).all()
    return templates.TemplateResponse(request, "index.html", {"categories": categories})


@app.post("/api/demos/{slug}/view")
def record_demo_view(slug: str, db: Session = Depends(get_db)):
    demo = db.scalar(select(Demo).where(Demo.slug == slug))
    if demo is None:
        raise HTTPException(status_code=404, detail="Demo not found")
    demo.view_count += 1
    db.commit()
    return {"slug": slug, "view_count": demo.view_count}
