"""Server-enforced admin access using current database permissions."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import security

router = APIRouter()


@router.get("/api/admin")
def admin_api(user=Depends(security.require_admin)):
    """Return the protected overview only after the current role is checked."""
    return {"message": "Admin access granted.", "username": user["username"]}


@router.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    """Use the same guard for a typed URL as for the API."""
    try:
        user = security.require_admin(request)
    except HTTPException as error:
        if error.status_code == 401:
            return RedirectResponse("/login", status_code=303)
        if error.status_code != 403:
            raise
        return request.app.state.templates.TemplateResponse(
            request=request, name="forbidden.html", context={}, status_code=403
        )
    return request.app.state.templates.TemplateResponse(
        request=request, name="admin.html", context={"user": user}
    )
