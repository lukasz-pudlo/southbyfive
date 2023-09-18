from django.urls import path
from classifications.views import ClassificationListView, ClassificationDetailView

app_name = 'classifications'

urlpatterns = [
    path('', ClassificationListView.as_view(),
         name='classification_list'),
    path('classification/<int:pk>/', ClassificationDetailView.as_view(),
         name='classification_detail')
]
