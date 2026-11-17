from django.urls import path

from results_import import views

app_name = "results_import"

urlpatterns = [
    path("", views.upload_list, name="list"),
    path("new/", views.upload_new, name="new"),
    path("rules/", views.rule_list, name="rules"),
    path("rules/<int:rule_id>/forget/", views.rule_forget, name="rule_forget"),
    path("<int:pk>/", views.upload_detail, name="detail"),
    path("<int:pk>/publish/", views.upload_publish, name="publish"),
    path("<int:pk>/revert/", views.upload_revert, name="revert"),
    path("<int:pk>/discard/", views.upload_discard, name="discard"),
    path("<int:pk>/reopen/", views.upload_reopen, name="reopen"),
    path("<int:pk>/original/", views.upload_original, name="original"),
    path("<int:pk>/converted/", views.upload_converted, name="converted"),
    path(
        "<int:pk>/changes/<int:change_id>/decide/",
        views.change_decide,
        name="change_decide",
    ),
    path(
        "<int:pk>/changes/<int:change_id>/revert/",
        views.change_revert,
        name="change_revert",
    ),
    path(
        "<int:pk>/changes/<int:change_id>/reapply/",
        views.change_reapply,
        name="change_reapply",
    ),
    path("<int:pk>/rows/<int:row_id>/edit/", views.row_edit, name="row_edit"),
    path(
        "<int:pk>/rows/<int:row_id>/use-file/<str:field>/",
        views.row_use_file,
        name="row_use_file",
    ),
]
