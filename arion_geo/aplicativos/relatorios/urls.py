from django.urls import path

from . import views


app_name = "relatorios"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("penalidades/claro/", views.claro_penalidades, name="claro-penalidades"),
    path("penalidades/claro/nova/", views.competence_create, name="competence-create"),
    path("penalidades/claro/verificar-periodo/", views.competence_period_exists, name="competence-period-exists"),
    path("penalidades/claro/<int:pk>/arquivo/", views.competence_upload, name="competence-upload"),
    path("penalidades/claro/<int:pk>/importar/", views.competence_import_review, name="import-review"),
    path("penalidades/claro/<int:pk>/original/baixar/", views.original_download, name="original-download"),
    path("tratativa/<int:pk>/", views.treatment_edit, name="treatment-edit"),
    path("tratativa/<int:pk>/detalhes/", views.treatment_detail_data, name="treatment-detail-data"),
    path("tratativa/<int:pk>/tickets/", views.treatment_ticket_relation, name="treatment-tickets"),
    path("tratativa/<int:pk>/enriquecer/", views.treatment_enrich, name="treatment-enrich"),
    path("tratativa/<int:pk>/editar-celula/", views.treatment_inline_edit, name="treatment-inline-edit"),
    path("tratativa/<int:pk>/pausas/", views.treatment_pause_add, name="treatment-pause-add"),
    path("tratativa/<int:pk>/pausas/<int:pause_pk>/remover/", views.treatment_pause_remove, name="treatment-pause-remove"),
    path("tratativa/<int:pk>/overrides/", views.treatment_override_add, name="treatment-override-add"),
    path("tratativa/<int:pk>/overrides/<int:override_pk>/remover/", views.treatment_override_remove, name="treatment-override-remove"),
    path("penalidades/claro/<int:pk>/", views.competence_workspace, name="workspace"),
    path("penalidades/claro/<int:pk>/finalizar/", views.competence_finalize, name="competence-finalize"),
    path("penalidades/claro/<int:pk>/reabrir/", views.competence_reopen, name="competence-reopen"),
    path("penalidades/claro/<int:pk>/excluir/", views.competence_delete, name="competence-delete"),
    path("penalidades/claro/<int:pk>/enriquecer/", views.competence_enrich, name="competence-enrich"),
    path("penalidades/claro/<int:pk>/exportar/", views.treatment_export, name="treatment-export"),
]
