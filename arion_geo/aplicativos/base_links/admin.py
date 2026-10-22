from django.contrib import admin

from .models import CMDBImport, CMDBLink, CMDBLinkChange, Operadora, Projeto, Provider


@admin.register(CMDBLink)
class CMDBLinkAdmin(admin.ModelAdmin):
    list_display = ("config_item_id", "designation_arion", "operadora", "projeto", "provider", "city", "uf", "deployment_state", "incident_state", "is_present_in_latest_import")
    search_fields = ("config_item_id", "designation_arion", "name", "address", "city", "isp_raw", "provider__name", "contract_number")
    list_filter = ("deployment_state", "incident_state", "uf", "classification_status", "operadora", "projeto", "provider")
    readonly_fields = ("first_seen_at", "last_seen_at", "synced_at", "created_at", "updated_at")
    list_select_related = ("operadora", "projeto", "provider", "last_seen_import")
    list_per_page = 50


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "cmdb_config_item_id", "active", "updated_at")
    search_fields = ("name", "normalized_name", "cmdb_config_item_id")
    list_filter = ("active",)


@admin.register(Operadora)
class OperadoraAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "updated_at")
    search_fields = ("name", "normalized_name")
    list_filter = ("active",)


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ("name", "active", "updated_at")
    search_fields = ("name", "normalized_name")
    list_filter = ("active",)


@admin.register(CMDBImport)
class CMDBImportAdmin(admin.ModelAdmin):
    list_display = ("filename", "created_at", "imported_by", "total_rows", "new_count", "updated_count", "unchanged_count", "error_count", "status")
    search_fields = ("filename", "file_sha256", "imported_by__username")
    list_filter = ("status", "created_at")
    readonly_fields = tuple(field.name for field in CMDBImport._meta.fields)
    list_per_page = 50


@admin.register(CMDBLinkChange)
class CMDBLinkChangeAdmin(admin.ModelAdmin):
    list_display = ("link", "field_name", "import_batch", "created_at")
    search_fields = ("link__config_item_id", "link__designation_arion", "field_name", "old_value", "new_value")
    list_filter = ("field_name", "created_at")
    readonly_fields = ("link", "import_batch", "field_name", "old_value", "new_value", "created_at")
    list_per_page = 50
