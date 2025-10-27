from django.templatetags.static import static
from django.conf import settings


def get_pj_icons(request):
    try:
        build = request.build_absolute_uri
    except Exception:  # pragma: no cover - safety for unusual call sites
        build = lambda p: p

    # Prefer locally served static assets so branding can be customized
    logo_url = build(static("logo.png"))
    favicon_url = build(static("img/favicon.png"))

    return {
        "jobopenings": logo_url,
        "logo": logo_url,
        "favicon": favicon_url,
        "cdn_path": settings.STATIC_URL,
    }
