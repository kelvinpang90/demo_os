from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.admin import auth, categories, demos
from app.admin.auth import require_login

router = APIRouter(prefix="/admin")
router.include_router(auth.router, tags=["admin-auth"])
router.include_router(categories.router, prefix="/categories", tags=["admin-categories"])
router.include_router(demos.router, prefix="/demos", tags=["admin-demos"])


@router.get("", dependencies=[Depends(require_login)])
def admin_root():
    return RedirectResponse("/admin/categories", status_code=303)
