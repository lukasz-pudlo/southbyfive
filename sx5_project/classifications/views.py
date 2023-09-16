from django.shortcuts import render
from django.views.generic import ListView, DetailView
from classifications.models import Classification, ClassificationResult


class ClassificationListView(ListView):
    model = Classification
    template_name = "classifications/classification_list.html"
    context_object_name = 'classifications'


class ClassificationDetailView(DetailView):
    model = Classification
    template_name = "classifications/classification_detail.html"
    context_object_name = 'classification'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['results'] = self.object.classification_results.all()
        return context
