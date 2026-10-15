from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_email_verified", "is_active")
    list_filter = ("role", "is_email_verified", "is_active")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("email",)
    actions = ["mark_email_verified"]

    fieldsets = UserAdmin.fieldsets + (
        ("ClinicBook", {"fields": ("role", "phone", "date_of_birth", "is_email_verified")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("ClinicBook", {"fields": ("email", "role", "phone", "date_of_birth", "is_email_verified")}),
    )

    @admin.action(description="Mark selected users' email as verified")
    def mark_email_verified(self, request, queryset):
        updated = queryset.update(is_email_verified=True)
        self.message_user(request, f"{updated} user(s) marked as verified.")