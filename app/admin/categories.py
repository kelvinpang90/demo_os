from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.auth import require_login
from app.database import get_db
from app.models import Category, Demo

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(dependencies=[Depends(require_login)])


@router.get("")
def list_categories(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
    return templates.TemplateResponse(
        request,
        "admin/categories.html",
        {"categories": categories, "error": request.query_params.get("error")},
    )


@router.get("/new")
def new_category_form(request: Request):
    return templates.TemplateResponse(
        request, "admin/category_form.html", {"category": None, "error": None}
    )


@router.post("/new")
def create_category(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Category).where(Category.slug == slug)):
        return templates.TemplateResponse(
            request,
            "admin/category_form.html",
            {"category": None, "error": "slug 已存在"},
            status_code=400,
        )
    db.add(
        Category(
            name=name,
            slug=slug,
            sort_order=sort_order,
            description=description or None,
        )
    )
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.get("/{category_id}/edit")
def edit_category_form(category_id: int, request: Request, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/category_form.html", {"category": category, "error": None}
    )


@router.post("/{category_id}/edit")
def update_category(
    category_id: int,
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)

    existing = db.scalar(
        select(Category).where(Category.slug == slug, Category.id != category_id)
    )
    if existing:
        return templates.TemplateResponse(
            request,
            "admin/category_form.html",
            {"category": category, "error": "slug 已存在"},
            status_code=400,
        )

    category.name = name
    category.slug = slug
    category.sort_order = sort_order
    category.description = description or None
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/{category_id}/delete")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404)

    demo_count = db.scalar(
        select(func.count()).select_from(Demo).where(Demo.category_id == category_id)
    )
    if demo_count:
        return RedirectResponse(
            "/admin/categories?error=该分类下还有 Demo，请先迁移或删除这些 Demo 后再删除分类",
            status_code=303,
        )

    db.delete(category)
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)
