from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('races/', include(('races.urls', 'races'), namespace='races')),
    path('race-versions/', include(('race_versions.urls',
         'race-versions'),  namespace='race-versions')),
    path('classifications/', include(('classifications.urls',
         'classifications'), namespace='classifications')),
    path('accounts/', include('django.contrib.auth.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
