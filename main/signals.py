from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CandidateProfile, ExaminerProfile, User


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create role-specific profile on user registration."""
    if not created:
        return
    if instance.role == User.Role.EXAMINER:
        ExaminerProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
