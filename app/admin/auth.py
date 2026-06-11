from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


def require_login(request: Request) -> None:
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})


@router.get("/login")
def login_form(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_username and password == settings.admin_password:
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": "用户名或密码错误"}, status_code=401
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
