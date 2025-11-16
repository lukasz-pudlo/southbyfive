from django.urls import path

from .views import contact, developer

app_name = "info"

urlpatterns = [
    path("contact/", contact, name="contact"),
    path("developer/", developer, name="developer"),
]
