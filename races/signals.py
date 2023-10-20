# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import Race


# @receiver(post_save, sender=Race)
# def post_race_save(sender, instance, created, **kwargs):
#     if created:  # Only run for newly created Race instances
#         from races.utils import create_result_versions
#         from races.utils import create_classification

#         create_result_versions(instance)
#         create_classification(instance)
