from django.urls import path
from django.urls import re_path
from classifications.views import ClassificationListView, ClassificationDetailView

app_name = 'classifications'

url_patterns = [
    re_path(r'^classifications/?$', ClassificationListView.as_view(),
            name='classification_list'),
    re_path(r'^classifications/(?P<pk>\d+)/?$',
            ClassificationDetailView.as_view(), name='classification_detail')
]
