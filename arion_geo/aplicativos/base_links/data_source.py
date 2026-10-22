def get_data_source_mode():
    from .models import CMDBImport

    return "cmdb" if CMDBImport.objects.exists() else "demo"
