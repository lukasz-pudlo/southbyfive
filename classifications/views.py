from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.db.models import Prefetch
from classifications.models import Classification, ClassificationResult


class ClassificationListView(ListView):
    model = Classification
    template_name = "classifications/classification_list.html"
    context_object_name = 'classifications'


class ClassificationDetailView(DetailView):
    model = Classification
    template_name = "classifications/classification_detail.html"
    context_object_name = 'classification'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classification = self.object
        classification_results_prefetch = Prefetch(
            'classification_results', queryset=ClassificationResult.objects.all().select_related('runner'))
        context['results'] = Classification.objects.prefetch_related(
            classification_results_prefetch).get(id=classification.id).classification_results.all()
        return context
