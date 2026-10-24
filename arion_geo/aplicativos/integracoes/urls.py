from django.urls import path

from . import views

app_name = "integracoes"

urlpatterns = [
    path("", views.home, name="home"),
    path("cmdb/", views.cmdb_detail, name="cmdb"),
    path("cmdb/testar/", views.cmdb_test, name="cmdb-test"),
    path("cmdb/diagnostico/", views.cmdb_diagnose, name="cmdb-diagnose"),
    path("otrs/", views.otrs_detail, name="otrs"),
    path("otrs/testar/", views.otrs_test, name="otrs-test"),
    path("otrs/estrutura/", views.otrs_schema, name="otrs-schema"),
    path("otrs/estrutura/<path:table_name>/", views.otrs_table_detail, name="otrs-table"),
    path("arion/", views.arion_detail, name="arion"),
    path("arion/salvar/", views.arion_save_configuration, name="arion-save"),
    path("arion/testar/", views.arion_test_connection, name="arion-test"),
    path("arion/etapa/<str:action>/", views.arion_migration_action, name="arion-action"),
    path("runs/", views.run_history, name="runs"),
    path("runs/<int:pk>/", views.run_detail, name="run-detail"),
    path("<str:key>/salvar/", views.save_configuration, name="save-config"),
    path("<str:key>/alternar/", views.toggle_integration, name="toggle"),
    path("<str:key>/remover-credenciais/", views.remove_credentials, name="remove-credentials"),
]
