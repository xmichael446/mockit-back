from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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
