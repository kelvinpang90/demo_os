import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.auth import require_login
from app.config import settings
from app.database import get_db
from app.models import Category, Demo

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(dependencies=[Depends(require_login)])

ALLOWED_THUMBNAIL_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _demo_dir(slug: str) -> Path:
    return Path(settings.demos_dir) / slug


def _prettify_name(text: str) -> str:
    cleaned = re.sub(r"[-_]+", " ", text).strip()
    return cleaned or text


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"demo-{uuid.uuid4().hex[:8]}"


def _unique_slug(db: Session, name: str, exclude_id: int | None = None) -> str:
    base = _slugify(name)
    slug = base
    suffix = 1
    while True:
        query = select(Demo).where(Demo.slug == slug)
        if exclude_id is not None:
            query = query.where(Demo.id != exclude_id)
        if db.scalar(query) is None:
            return slug
        suffix += 1
        slug = f"{base}-{suffix}"


def _safe_extract_zip(zip_path: Path, dest: Path) -> None:
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            member_path = (dest / member).resolve()
            if dest_resolved != member_path and dest_resolved not in member_path.parents:
                raise HTTPException(status_code=400, detail="ZIP 中包含非法路径")
        zf.extractall(dest)


def _replace_demo_files(slug: str, source: Path) -> None:
    if not (source / "index.html").exists():
        raise HTTPException(status_code=400, detail="上传内容中未找到 index.html，请检查后重新上传")

    dest = _demo_dir(slug)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))


def _save_thumbnail(slug: str, file: UploadFile) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_THUMBNAIL_EXTS:
        raise HTTPException(status_code=400, detail="缩略图仅支持 jpg/png/webp 格式")

    thumbnails_dir = Path(settings.thumbnails_dir)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    dest = thumbnails_dir / f"{slug}{ext}"
    with dest.open("wb") as out:
        out.write(file.file.read())

    return f"/thumbnails/{dest.name}"


def _stage_zip_upload(zip_file: UploadFile, tmp_path: Path) -> tuple[Path, str]:
    zip_path = tmp_path / "upload.zip"
    with zip_path.open("wb") as out:
        shutil.copyfileobj(zip_file.file, out)

    extract_dir = tmp_path / "extracted"
    _safe_extract_zip(zip_path, extract_dir)

    entries = list(extract_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0], entries[0].name
    return extract_dir, Path(zip_file.filename).stem


def _stage_folder_upload(files: list[UploadFile], tmp_path: Path) -> tuple[Path, str | None]:
    staging = tmp_path / "staging"
    staging.mkdir()
    name_hint = None
    for f in files:
        parts = Path(f.filename or "").parts
        if not parts:
            continue
        if name_hint is None:
            name_hint = parts[0]
        rel_parts = parts[1:] if len(parts) > 1 else parts
        if not rel_parts or ".." in rel_parts:
            continue
        target = staging / Path(*rel_parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            shutil.copyfileobj(f.file, out)
    return staging, name_hint


def _generate_screenshot(slug: str) -> str | None:
    index_path = _demo_dir(slug) / "index.html"
    if not index_path.exists():
        return None

    thumbnails_dir = Path(settings.thumbnails_dir)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    dest = thumbnails_dir / f"{slug}.png"

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(index_path.resolve().as_uri(), wait_until="load", timeout=15000)
            page.screenshot(path=str(dest))
            browser.close()
    except Exception:
        return None

    return f"/thumbnails/{dest.name}"


def _delete_thumbnail(thumbnail_path: str | None) -> None:
    if not thumbnail_path:
        return
    file_path = Path(settings.thumbnails_dir) / Path(thumbnail_path).name
    file_path.unlink(missing_ok=True)


@router.get("")
def list_demos(request: Request, db: Session = Depends(get_db)):
    demos = db.scalars(
        select(Demo).order_by(Demo.category_id, Demo.sort_order, Demo.id)
    ).all()
    return templates.TemplateResponse(request, "admin/demos.html", {"demos": demos})


@router.get("/new")
def new_demo_form(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
    return templates.TemplateResponse(
        request, "admin/demo_form.html", {"demo": None, "categories": categories, "error": None}
    )


@router.post("/new")
def create_demo(
    request: Request,
    name: str = Form(""),
    slug: str = Form(""),
    category_id: int = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    thumbnail: UploadFile | None = File(None),
    zip_file: UploadFile | None = File(None),
    folder_files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
):
    name = name.strip()
    slug = slug.strip()

    def error_response(message: str):
        categories = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
        return templates.TemplateResponse(
            request,
            "admin/demo_form.html",
            {"demo": None, "categories": categories, "error": message},
            status_code=400,
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staged_dir: Path | None = None
        name_hint: str | None = None

        if zip_file and zip_file.filename:
            try:
                staged_dir, name_hint = _stage_zip_upload(zip_file, tmp_path)
            except (zipfile.BadZipFile, HTTPException) as exc:
                detail = "无效的 ZIP 文件" if isinstance(exc, zipfile.BadZipFile) else exc.detail
                return error_response(detail)
        elif folder_files and folder_files[0].filename:
            staged_dir, name_hint = _stage_folder_upload(folder_files, tmp_path)

        if staged_dir is not None and not (staged_dir / "index.html").exists():
            return error_response("上传内容中未找到 index.html，请检查后重新上传")

        if not name:
            if not name_hint:
                return error_response("请填写名称，或上传 ZIP/文件夹以自动识别")
            name = _prettify_name(name_hint)

        if not slug:
            slug = _unique_slug(db, name_hint or name)
        elif db.scalar(select(Demo).where(Demo.slug == slug)):
            return error_response("slug 已存在")

        thumbnail_path = None
        if thumbnail and thumbnail.filename:
            thumbnail_path = _save_thumbnail(slug, thumbnail)

        demo = Demo(
            name=name,
            slug=slug,
            category_id=category_id,
            description=description or None,
            thumbnail_path=thumbnail_path,
            sort_order=sort_order,
        )
        db.add(demo)
        db.commit()

        if staged_dir is not None:
            _replace_demo_files(slug, staged_dir)
            if thumbnail_path is None:
                demo.thumbnail_path = _generate_screenshot(slug)
                db.commit()

    return RedirectResponse("/admin/demos", status_code=303)


@router.get("/{demo_id}/edit")
def edit_demo_form(demo_id: int, request: Request, db: Session = Depends(get_db)):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)
    categories = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
    has_files = (_demo_dir(demo.slug) / "index.html").exists()
    return templates.TemplateResponse(
        request,
        "admin/demo_form.html",
        {
            "demo": demo,
            "categories": categories,
            "error": request.query_params.get("error"),
            "msg": request.query_params.get("msg"),
            "has_files": has_files,
        },
    )


@router.post("/{demo_id}/edit")
def update_demo(
    demo_id: int,
    request: Request,
    name: str = Form(...),
    slug: str = Form(""),
    category_id: int = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    thumbnail: UploadFile | None = File(None),
    remove_thumbnail: bool = Form(False),
    db: Session = Depends(get_db),
):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)

    slug = slug.strip()
    if not slug:
        slug = _unique_slug(db, name, exclude_id=demo_id)

    existing = db.scalar(select(Demo).where(Demo.slug == slug, Demo.id != demo_id))
    if existing:
        categories = db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()
        return templates.TemplateResponse(
            request,
            "admin/demo_form.html",
            {"demo": demo, "categories": categories, "error": "slug 已存在"},
            status_code=400,
        )

    if thumbnail and thumbnail.filename:
        _delete_thumbnail(demo.thumbnail_path)
        demo.thumbnail_path = _save_thumbnail(slug, thumbnail)
    elif remove_thumbnail:
        _delete_thumbnail(demo.thumbnail_path)
        demo.thumbnail_path = None

    old_slug = demo.slug
    demo.name = name
    demo.slug = slug
    demo.category_id = category_id
    demo.description = description or None
    demo.sort_order = sort_order
    db.commit()

    if old_slug != slug:
        old_dir = _demo_dir(old_slug)
        if old_dir.exists():
            new_dir = _demo_dir(slug)
            if new_dir.exists():
                shutil.rmtree(new_dir)
            shutil.move(str(old_dir), str(new_dir))

    return RedirectResponse("/admin/demos", status_code=303)


@router.post("/{demo_id}/delete")
def delete_demo(demo_id: int, db: Session = Depends(get_db)):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)

    _delete_thumbnail(demo.thumbnail_path)
    shutil.rmtree(_demo_dir(demo.slug), ignore_errors=True)
    db.delete(demo)
    db.commit()
    return RedirectResponse("/admin/demos", status_code=303)


@router.post("/{demo_id}/files/zip")
def upload_demo_zip(
    demo_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)

    if Path(file.filename or "").suffix.lower() != ".zip":
        return RedirectResponse(
            f"/admin/demos/{demo_id}/edit?error={quote('请上传 ZIP 文件')}", status_code=303
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "upload.zip"
        with zip_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        extract_dir = tmp_path / "extracted"
        try:
            _safe_extract_zip(zip_path, extract_dir)
        except (zipfile.BadZipFile, HTTPException) as exc:
            detail = "无效的 ZIP 文件" if isinstance(exc, zipfile.BadZipFile) else exc.detail
            return RedirectResponse(
                f"/admin/demos/{demo_id}/edit?error={quote(detail)}", status_code=303
            )

        entries = list(extract_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            extract_dir = entries[0]

        try:
            _replace_demo_files(demo.slug, extract_dir)
        except HTTPException as exc:
            return RedirectResponse(
                f"/admin/demos/{demo_id}/edit?error={quote(exc.detail)}", status_code=303
            )

    if demo.thumbnail_path is None:
        demo.thumbnail_path = _generate_screenshot(demo.slug)
        db.commit()

    return RedirectResponse(
        f"/admin/demos/{demo_id}/edit?msg={quote('文件上传成功')}", status_code=303
    )


@router.post("/{demo_id}/files/folder")
def upload_demo_folder(
    demo_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)

    if not files or not files[0].filename:
        return RedirectResponse(
            f"/admin/demos/{demo_id}/edit?error={quote('请选择文件夹')}", status_code=303
        )

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "staging"
        staging.mkdir()

        for f in files:
            parts = Path(f.filename).parts
            if len(parts) > 1:
                parts = parts[1:]
            if not parts or ".." in parts:
                continue

            target = staging / Path(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                shutil.copyfileobj(f.file, out)

        try:
            _replace_demo_files(demo.slug, staging)
        except HTTPException as exc:
            return RedirectResponse(
                f"/admin/demos/{demo_id}/edit?error={quote(exc.detail)}", status_code=303
            )

    if demo.thumbnail_path is None:
        demo.thumbnail_path = _generate_screenshot(demo.slug)
        db.commit()

    return RedirectResponse(
        f"/admin/demos/{demo_id}/edit?msg={quote('文件上传成功')}", status_code=303
    )


@router.post("/{demo_id}/reset-views")
def reset_views(demo_id: int, db: Session = Depends(get_db)):
    demo = db.get(Demo, demo_id)
    if demo is None:
        raise HTTPException(status_code=404)

    demo.view_count = 0
    db.commit()
    return RedirectResponse("/admin/demos", status_code=303)
