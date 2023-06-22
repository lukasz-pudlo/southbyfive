from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('races/', include(('races.urls', 'races'), namespace='races'))
]
