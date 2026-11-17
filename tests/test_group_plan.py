"""Check that teammates can read the hosted draft and reach its shared source."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_group_draft_is_public_with_working_styles_and_github_edit_link(settings):
    """The complete draft opens without a workspace account or relaxed CSP."""
    with TestClient(create_app(settings), base_url=settings.origin) as browser:
        response = browser.get("/group-plan")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "3. Group content system + problem research" in response.text
        assert "Newark Briefing Desk" in response.text
        assert "https://github.com/Y-Just-Y/is373_ci_cd/edit/main/group-plan.html" in (
            response.text
        )
        assert "chatgpt.com/space/" not in response.text
        assert '<link rel="stylesheet" href="/static/group-plan.css">' in response.text
        assert "<style>" not in response.text
        assert "<script" not in response.text
        assert "style-src 'self'" in response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        styles = browser.get("/static/group-plan.css")
        assert styles.status_code == 200
        assert ".plan-nav" in styles.text


def test_published_group_draft_is_separate_from_private_files(settings):
    """A reviewed update can be published without serving symlinked private data."""
    application = create_app(settings)
    public = settings.database.parent / "public"
    public.mkdir(mode=0o700)
    published = public / "group-plan.html"
    published.write_text("<h1>Reviewed group update</h1>", encoding="utf-8")
    with TestClient(application, base_url=settings.origin) as browser:
        assert browser.get("/group-plan").text == "<h1>Reviewed group update</h1>"
        published.unlink()
        private = settings.database.parent / "private-example.txt"
        private.write_text("This private value must never be served.", encoding="utf-8")
        published.symlink_to(private)
        response = browser.get("/group-plan")
        assert response.status_code == 200
        assert "Newark Briefing Desk" in response.text
        assert "This private value" not in response.text
