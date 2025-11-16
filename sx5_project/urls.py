from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from races.views import custom_404, home

# Custom 404 handler
handler404 = "races.views.custom_404"

urlpatterns = [
    path("admin/", admin.site.urls),  # Admin interface
    path("", home, name="home"),  # Home page
    path("races/", include(("races.urls", "races"), namespace="races")),  # Races app
    path(
        "race-versions/",
        include(("race_versions.urls", "race-versions"), namespace="race-versions"),
    ),  # Race versions app
    path(
        "classifications/",
        include(
            ("classifications.urls", "classifications"), namespace="classifications"
        ),
    ),  # Classifications app
    path("accounts/", include("django.contrib.auth.urls")),  # Authentication
    path("info/", include(("info.urls", "info"), namespace="info")),  # Info app
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
