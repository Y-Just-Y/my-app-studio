"""A public professional portfolio, separate from the civic product's identity."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/portfolio", include_in_schema=False)
def portfolio_home(request: Request):
    """Let a visitor inspect the student's direction, projects and evidence."""
    return request.app.state.templates.TemplateResponse(
        request=request, name="portfolio.html", context={}
    )


@router.get("/portfolio/projects/asteri", include_in_schema=False)
def asteri_case_study(request: Request):
    """Present a public summary without exposing the private project sources."""
    return request.app.state.templates.TemplateResponse(
        request=request, name="portfolio_asteri.html", context={}
    )
