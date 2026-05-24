from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from sx5_project.middleware import FrameAncestorsMiddleware


HEALTHZ_URL = "/healthz/"


@override_settings(
    ALLOWED_FRAME_ANCESTORS=[
        "'self'",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8010",
        "http://127.0.0.1:8010",
    ],
)
def test_local_portfolio_can_embed_site(client):
    response = client.get(HEALTHZ_URL)

    csp = response.headers.get("Content-Security-Policy", "")

    assert "frame-ancestors" in csp
    assert "'self'" in csp
    assert "http://localhost:8000" in csp
    assert "http://127.0.0.1:8000" in csp
    assert "http://localhost:8010" in csp
    assert response.headers.get("X-Frame-Options") not in {"DENY", "SAMEORIGIN"}


@override_settings(ALLOWED_FRAME_ANCESTORS=["'self'"])
def test_production_self_only_keeps_x_frame_options(client):
    response = client.get(HEALTHZ_URL)

    csp = response.headers.get("Content-Security-Policy", "")

    assert "frame-ancestors 'self'" in csp
    assert "localhost" not in csp
    assert "127.0.0.1" not in csp
    # 'self' alone is equivalent to SAMEORIGIN — leave X-Frame-Options in place
    # so that older browsers still get clickjacking protection.
    assert response.headers.get("X-Frame-Options") in {"DENY", "SAMEORIGIN"}


@override_settings(
    ALLOWED_FRAME_ANCESTORS=[
        "'self'",
        "https://lukaszpudlo.com",
        "https://www.lukaszpudlo.com",
    ],
)
def test_production_portfolio_can_embed_site(client):
    response = client.get(HEALTHZ_URL)

    csp = response.headers.get("Content-Security-Policy", "")

    assert "frame-ancestors" in csp
    assert "https://lukaszpudlo.com" in csp
    assert "https://www.lukaszpudlo.com" in csp
    assert "localhost" not in csp
    assert response.headers.get("X-Frame-Options") not in {"DENY", "SAMEORIGIN"}


@override_settings(
    ALLOWED_FRAME_ANCESTORS=["'self'", "http://localhost:8000"],
)
def test_csp_preserves_existing_directives():
    def get_response(_request):
        response = HttpResponse("ok")
        response["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
        response["X-Frame-Options"] = "DENY"
        return response

    middleware = FrameAncestorsMiddleware(get_response)
    request = RequestFactory().get("/")
    response = middleware(request)

    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "img-src 'self' data:" in csp
    # Original frame-ancestors 'none' must be replaced, not appended next to.
    assert "frame-ancestors 'none'" not in csp
    assert "http://localhost:8000" in csp
    # Cross-origin embedding is allowed, so X-Frame-Options must be stripped.
    assert "X-Frame-Options" not in response


@override_settings(
    ALLOWED_FRAME_ANCESTORS=["'self'", "http://localhost:8000"],
)
def test_x_frame_options_stripped_when_cross_origin_allowed(client):
    response = client.get(HEALTHZ_URL)

    assert response.headers.get("X-Frame-Options") not in {"DENY", "SAMEORIGIN"}
    assert "frame-ancestors" in response.headers.get("Content-Security-Policy", "")
