from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CandidateProfile, ExaminerCredential, ExaminerProfile, ScoreHistory, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'role', 'max_sessions', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Limits', {'fields': ('role', 'max_sessions')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role & Limits', {'fields': ('role', 'max_sessions')}),
    )


@admin.register(ExaminerProfile)
class ExaminerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_legal_name", "is_verified", "completed_session_count")
    list_filter = ("is_verified",)
    readonly_fields = ("completed_session_count",)
    search_fields = ("user__username", "full_legal_name")


@admin.register(ExaminerCredential)
class ExaminerCredentialAdmin(admin.ModelAdmin):
    list_display = ("examiner_profile", "listening_score", "reading_score", "writing_score", "speaking_score")
    search_fields = ("examiner_profile__user__username",)


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "target_speaking_score", "current_speaking_score")
    search_fields = ("user__username",)


@admin.register(ScoreHistory)
class ScoreHistoryAdmin(admin.ModelAdmin):
    list_display = ("candidate_profile", "session", "overall_band", "created_at")
    list_filter = ("overall_band",)
    readonly_fields = ("candidate_profile", "session", "overall_band")
