from django.urls import path

from .views import contact

app_name = "info"

urlpatterns = [
    path("contact/", contact, name="contact"),
]
