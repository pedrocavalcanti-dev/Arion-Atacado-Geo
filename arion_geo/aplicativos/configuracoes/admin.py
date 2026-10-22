from django.contrib import admin

from .models import UserDataScope, UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "theme", "updated_at")
    list_filter = ("theme",)


@admin.register(UserDataScope)
class UserDataScopeAdmin(admin.ModelAdmin):
    list_display = ("user", "mode", "updated_at")
    list_filter = ("mode",)
    filter_horizontal = ("allowed_operators", "allowed_projects")
    search_fields = ("user__username",)
