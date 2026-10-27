"""Member account HTML and JSON routes using the prepared security services."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import security
from app.schemas import LoginInput, PublicUser, SignupInput

router = APIRouter()


def api_csrf(request: Request):
    """Validate the session-bound header before any API mutation."""
    security.require_csrf(request, request.headers.get("X-CSRF-Token"))


@router.get("/api/csrf")
def csrf(request: Request, response: Response):
    """Issue the same-origin synchronizer token."""
    return {"csrf_token": security.csrf_token(request, response)}


@router.post(
    "/api/signup",
    status_code=201,
    response_model=PublicUser,
    dependencies=[Depends(api_csrf)],
)
def signup_api(credentials: SignupInput, request: Request):
    """Create only regular members."""
    security.limit_signup(request)
    return security.signup(
        request.app.state.settings, credentials.username, credentials.password
    )


@router.post("/api/login", response_model=PublicUser, dependencies=[Depends(api_csrf)])
def login_api(credentials: LoginInput, request: Request, response: Response):
    """Authenticate with an HttpOnly cookie; return public identity only."""
    return security.login(request, response, credentials.username, credentials.password)


@router.get("/api/me", response_model=PublicUser)
def me(user=Depends(security.require_user)):
    """Require a current, unrevoked session."""
    return user


@router.post("/api/logout", dependencies=[Depends(api_csrf)])
def logout_api(request: Request, response: Response):
    """Revoke server state and clear the browser cookie."""
    security.logout(request, response)
    return {"message": "Logged out."}


def render(request, name, context=None, status=200):
    """Render a form with a token, forwarding any new session cookie."""
    cookie_response = Response()
    values = dict(context or {})
    values["csrf_token"] = security.csrf_token(request, cookie_response)
    response = request.app.state.templates.TemplateResponse(
        request=request, name=name, context=values, status_code=status
    )
    for key, value in cookie_response.raw_headers:
        if key == b"set-cookie":
            response.raw_headers.append((key, value))
    return response


@router.get("/signup", include_in_schema=False)
@router.get("/login", include_in_schema=False)
def account_form(request: Request):
    """Show the appropriate account form or the existing member space."""
    if security.authenticate(request):
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "account.html", {"signup": request.url.path == "/signup"})


@router.post("/signup", include_in_schema=False)
@router.post("/login", include_in_schema=False)
async def submit_account(request: Request):
    """Share validation and security behavior with the JSON endpoints."""
    signup = request.url.path == "/signup"
    username = ""
    try:
        async with request.form(max_fields=3, max_files=0) as form:
            security.require_csrf(request, form.get("csrf_token"))
            values = {key: value for key, value in form.items() if key != "csrf_token"}
            if len(form.multi_items()) != len(form):
                raise HTTPException(422, "Submit each field once.")
            credentials = (SignupInput if signup else LoginInput).model_validate(values)
        username = credentials.username
        if signup:
            security.limit_signup(request)
            security.signup(request.app.state.settings, username, credentials.password)
            return RedirectResponse("/login?created=1", status_code=303)
        response = RedirectResponse("/dashboard", status_code=303)
        security.login(request, response, username, credentials.password)
        return response
    except ValidationError:
        return render(
            request,
            "account.html",
            {
                "signup": signup,
                "error": "Check your username and password requirements.",
            },
            status=422,
        )
    except HTTPException as error:
        response = render(
            request,
            "account.html",
            {"signup": signup, "username": username, "error": error.detail},
            status=error.status_code,
        )
        response.headers.update(error.headers or {})
        return response


@router.get("/dashboard", include_in_schema=False)
def dashboard(request: Request):
    """Redirect anonymous visitors, and render the authenticated member only."""
    user = security.authenticate(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return render(request, "dashboard.html", {"user": user})


@router.post("/logout", include_in_schema=False)
async def logout_form(request: Request):
    """Require a valid form token before revoking the session."""
    async with request.form(max_fields=1, max_files=0) as form:
        security.require_csrf(request, form.get("csrf_token"))
    response = RedirectResponse("/login", status_code=303)
    security.logout(request, response)
    return response
