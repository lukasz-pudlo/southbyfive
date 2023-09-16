from django.urls import path
from django.urls import re_path
from races.views import RaceListView, RaceDetailView, RaceCreateView, RaceUpdateView, RaceDeleteView

app_name = 'races'

urlpatterns = [
    re_path(r'^$', RaceListView.as_view(), name='list'),
    re_path(r'^race/(?P<pk>\d+)/?$', RaceDetailView.as_view(), name='detail'),
    re_path(r'^race/new/?$', RaceCreateView.as_view(), name='new'),
    re_path(r'^race/(?P<pk>\d+)/edit/?$',
            RaceUpdateView.as_view(), name='edit'),
    re_path(r'^race/(?P<pk>\d+)/delete/?$',
            RaceDeleteView.as_view(), name='delete')
]
