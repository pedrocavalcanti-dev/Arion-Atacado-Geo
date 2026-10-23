import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


PERMISSIONS = (
    "view_dashboard", "view_cockpit", "save_analytics_views", "view_map",
    "view_rankings", "view_base", "import_cmdb", "export_base",
    "manage_users", "manage_groups", "manage_data_scopes", "view_audit_log",
    "view_integrations", "view_system_info", "view_ari",
)


def migrate_group_scopes(apps, schema_editor):
    alias = schema_editor.connection.alias
    Group = apps.get_model("auth", "Group")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    GroupDataScope = apps.get_model("configuracoes", "GroupDataScope")
    LegacyScope = apps.get_model("configuracoes", "UserDataScope")
    through_operator = LegacyScope.allowed_operators.through
    through_project = LegacyScope.allowed_projects.through

    old_type = ContentType.objects.using(alias).filter(app_label="configuracoes", model="userdatascope").first()
    new_type, _ = ContentType.objects.using(alias).get_or_create(app_label="configuracoes", model="groupdatascope")
    if old_type:
        Permission.objects.using(alias).filter(content_type_id=old_type.pk, codename__in=PERMISSIONS).update(content_type_id=new_type.pk)

    user_model = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    for group in Group.objects.using(alias).all().iterator():
        default_mode = "all" if group.name == "Administrador do Sistema" else "custom"
        scope, created = GroupDataScope.objects.using(alias).get_or_create(group_id=group.pk, defaults={"mode": default_mode})
        if not created or group.name == "Administrador do Sistema":
            continue
        members = list(user_model.objects.using(alias).filter(groups__id=group.pk).values_list("id", flat=True))
        legacy = list(LegacyScope.objects.using(alias).filter(user_id__in=members).values("id", "user_id", "mode"))
        if not members or len(legacy) != len(members):
            continue
        signatures = []
        for row in legacy:
            operator_ids = tuple(sorted(through_operator.objects.using(alias).filter(userdatascope_id=row["id"]).values_list("operadora_id", flat=True)))
            project_ids = tuple(sorted(through_project.objects.using(alias).filter(userdatascope_id=row["id"]).values_list("projeto_id", flat=True)))
            signatures.append((row["mode"], operator_ids, project_ids))
        if signatures and all(signature == signatures[0] for signature in signatures):
            mode, operator_ids, project_ids = signatures[0]
            scope.mode = mode
            scope.save(using=alias, update_fields=["mode"])
            if operator_ids:
                scope.allowed_operators.set(operator_ids)
            if project_ids:
                scope.allowed_projects.set(project_ids)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("base_links", "0002_alter_cmdblink_range_ip"),
        ("configuracoes", "0005_alter_userdatascope_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupDataScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("all", "Todos os dados"), ("custom", "Personalizado")], default="custom", max_length=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("allowed_operators", models.ManyToManyField(blank=True, related_name="scoped_groups", to="base_links.operadora")),
                ("allowed_projects", models.ManyToManyField(blank=True, related_name="scoped_groups", to="base_links.projeto")),
                ("group", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="data_scope", to="auth.group")),
            ],
            options={
                "verbose_name": "escopo de dados do grupo",
                "verbose_name_plural": "escopos de dados dos grupos",
                "permissions": [(codename, f"Can {codename.replace('_', ' ')}") for codename in PERMISSIONS],
            },
        ),
        migrations.RunPython(migrate_group_scopes, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="UserDataScope", new_name="LegacyUserDataScope"),
                migrations.AlterModelTable(name="legacyuserdatascope", table="configuracoes_userdatascope"),
                migrations.AlterModelOptions(name="legacyuserdatascope", options={
                    "verbose_name": "escopo legado de usuário",
                    "verbose_name_plural": "escopos legados de usuários",
                }),
                migrations.AlterField(model_name="legacyuserdatascope", name="user", field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="legacy_data_scope", to=settings.AUTH_USER_MODEL)),
                migrations.AlterField(model_name="legacyuserdatascope", name="allowed_operators", field=models.ManyToManyField(blank=True, db_table="configuracoes_userdatascope_allowed_operators", related_name="legacy_scoped_users", to="base_links.operadora")),
                migrations.AlterField(model_name="legacyuserdatascope", name="allowed_projects", field=models.ManyToManyField(blank=True, db_table="configuracoes_userdatascope_allowed_projects", related_name="legacy_scoped_users", to="base_links.projeto")),
            ],
        ),
    ]
