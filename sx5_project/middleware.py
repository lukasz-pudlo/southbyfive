from django.conf import settings


class FrameAncestorsMiddleware:
    """Sets a `Content-Security-Policy: frame-ancestors ...` header on every response.

    Reads the allowed origins from `settings.ALLOWED_FRAME_ANCESTORS`. Preserves any
    existing CSP directives. When non-self origins are allowed, also strips the
    `X-Frame-Options` header set by Django's clickjacking middleware so that
    cross-origin iframe embedding is not blocked by the older header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        ancestors = list(getattr(settings, "ALLOWED_FRAME_ANCESTORS", ["'self'"]))
        if not ancestors:
            return response

        directive = "frame-ancestors " + " ".join(ancestors)

        existing = response.get("Content-Security-Policy", "")
        directives = [
            item.strip()
            for item in existing.split(";")
            if item.strip() and not item.strip().startswith("frame-ancestors")
        ]
        directives.append(directive)
        response["Content-Security-Policy"] = "; ".join(directives)

        only_self = [a.strip() for a in ancestors] == ["'self'"]
        if not only_self and response.has_header("X-Frame-Options"):
            del response["X-Frame-Options"]

        return response
