from django.contrib import admin

from .models import GroupDataScope, LegacyUserDataScope, UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "theme", "updated_at")
    list_filter = ("theme",)


@admin.register(GroupDataScope)
class GroupDataScopeAdmin(admin.ModelAdmin):
    list_display = ("group", "mode", "updated_at")
    list_filter = ("mode",)
    filter_horizontal = ("allowed_operators", "allowed_projects")
    search_fields = ("group__name",)


@admin.register(LegacyUserDataScope)
class LegacyUserDataScopeAdmin(admin.ModelAdmin):
    list_display = ("user", "mode", "updated_at")
    readonly_fields = ("user", "mode", "created_at", "updated_at", "allowed_operators", "allowed_projects")
    search_fields = ("user__username",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
