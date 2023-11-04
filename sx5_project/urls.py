from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from races.views import home
from django.conf.urls import handler404
from races.views import custom_404

handler404 = 'races.views.custom_404'

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('', RedirectView.as_view(url='races/', permanent=False)),
    path('', home, name='home'),
    path('races/', include(('races.urls', 'races'), namespace='races')),
    path('race-versions/', include(('race_versions.urls',
         'race-versions'),  namespace='race-versions')),
    path('classifications/', include(('classifications.urls',
         'classifications'), namespace='classifications')),
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
