import csv
import json

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from aplicativos.base_links.models import CMDBLink
from .access_control import ADMIN_PERMISSIONS, GROUP_SYSTEM_ADMIN, PERMISSION_LABELS, is_system_admin
from .admin_forms import AccessGroupForm, UserCreateForm, UserDataScopeForm, UserUpdateForm
from .data_scope import DataScopeService
from .forms import AccountForm
from .models import UserPreference
from .models import UserDataScope
from .permissions import access_required
from aplicativos.auditoria.models import AuditEvent
from aplicativos.base_links.models import CMDBImport
from django.conf import settings
from django.db import connections
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from aplicativos.auditoria.services import AuditService


@login_required
def account(request):
    if request.method == "POST":
        form = AccountForm(request.POST, instance=request.user)
        if form.is_valid():
            before = {"first_name": request.user.first_name, "last_name": request.user.last_name, "email": request.user.email}
            form.save()
            after = {"first_name": request.user.first_name, "last_name": request.user.last_name, "email": request.user.email}
            if before != after:
                AuditService.record(request=request, user=request.user, category="ACCOUNT", action="ACCOUNT_UPDATED", module="Conta", description="Dados da conta atualizados", obj=request.user, metadata={"before": before, "after": after})
            messages.success(request, "Seus dados foram atualizados.")
            return redirect("configuracoes:account")
    else:
        form = AccountForm(instance=request.user)
    return render(request, "configuracoes/account.html", _settings_context(request, "account", form=form))


@login_required
def index(request):
    return render(request, "configuracoes/index.html", _settings_context(request, "index"))


@login_required
def security(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            AuditService.record(request=request, user=user, category="ACCOUNT", action="PASSWORD_CHANGED", description="Senha alterada pelo próprio usuário", obj=user)
            messages.success(request, "Sua senha foi alterada com segurança.")
            return redirect("configuracoes:security")
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, "configuracoes/security.html", _settings_context(request, "security", form=form))


@login_required
def appearance(request):
    preference, _ = UserPreference.objects.get_or_create(user=request.user)
    return render(request, "configuracoes/appearance.html", _settings_context(request, "appearance", preference=preference))


def _settings_context(request, active_section, **extra):
    return {"active_section": active_section, "is_access_admin": is_system_admin(request.user), **extra}


def _admin_context(request, section, **extra):
    return _settings_context(request, section, administration=True, **extra)


def _active_system_admins():
    users = get_user_model().objects.filter(is_active=True, is_superuser=False).prefetch_related("groups__permissions")
    return [user for user in users if is_system_admin(user)]


def _groups_have_system_admin_access(groups):
    codenames = set(Permission.objects.filter(
        group__in=groups, content_type__app_label="configuracoes",
        codename__in=ADMIN_PERMISSIONS,
    ).values_list("codename", flat=True))
    return set(ADMIN_PERMISSIONS).issubset(codenames)


@login_required
@access_required("manage_users")
def user_list(request):
    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group", "")
    status = request.GET.get("status", "")
    users = get_user_model().objects.all().prefetch_related("groups", "data_scope__allowed_operators", "data_scope__allowed_projects")
    if query:
        users = users.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query) | Q(email__icontains=query))
    if group_id.isdigit():
        users = users.filter(groups__id=int(group_id))
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)
    users = users.distinct().order_by("username")
    page_obj = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(request, "configuracoes/admin/users.html", _admin_context(request, "users", page_obj=page_obj, groups=Group.objects.order_by("name"), filters={"q": query, "group": group_id, "status": status}))


@login_required
@access_required("manage_users")
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        AuditService.record(request=request, category="ADMINISTRATION", action="USER_CREATED", description="Usuário criado", obj=user, metadata={
            "user_id": user.pk, "username": user.username, "groups": list(user.groups.order_by("name").values_list("name", flat=True)),
            "scope_mode": user.data_scope.mode,
        })
        messages.success(request, "Usuário criado.")
        return redirect("configuracoes:user-detail", pk=user.pk)
    return render(request, "configuracoes/admin/user_form.html", _admin_context(request, "users", form=form, page_title="Novo usuário", user_object=None))


@login_required
@access_required("manage_users")
def user_detail(request, pk):
    user = get_object_or_404(get_user_model().objects.prefetch_related("groups", "data_scope__allowed_operators", "data_scope__allowed_projects"), pk=pk)
    return render(request, "configuracoes/admin/user_detail.html", _admin_context(request, "users", user_object=user, data_scope=DataScopeService.get_scope(user)))


@login_required
@access_required("manage_users")
def user_edit(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    was_active_system_admin = user.is_active and is_system_admin(user)
    before_profile = {field: getattr(user, field) for field in ("first_name", "last_name", "email")}
    groups_before = list(user.groups.order_by("name").values_list("name", flat=True))
    scope_before = getattr(user, "data_scope", None)
    mode_before = scope_before.mode if scope_before else UserDataScope.Mode.ALL
    operators_before = list(scope_before.allowed_operators.order_by("name").values_list("name", flat=True)) if scope_before else []
    projects_before = list(scope_before.allowed_projects.order_by("name").values_list("name", flat=True)) if scope_before else []
    was_active = user.is_active
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if was_active_system_admin and len(_active_system_admins()) <= 1:
            if not form.cleaned_data["is_active"] or not _groups_have_system_admin_access(form.cleaned_data["groups"]):
                form.add_error(None, "Não é possível remover ou desativar o último Administrador do Sistema ativo.")
        if not form.errors:
            with transaction.atomic():
                form.save()
            profile_after = {field: getattr(user, field) for field in ("first_name", "last_name", "email")}
            if before_profile != profile_after:
                AuditService.record(request=request, category="ADMINISTRATION", action="USER_UPDATED", description="Dados gerais do usuário atualizados", obj=user, metadata={"before": before_profile, "after": profile_after})
            groups_after = list(user.groups.order_by("name").values_list("name", flat=True))
            if groups_before != groups_after:
                AuditService.record(request=request, category="ADMINISTRATION", action="GROUP_CHANGED", description="Grupos de acesso alterados", obj=user, metadata={"before": groups_before, "after": groups_after})
            scope_after = UserDataScope.objects.get(user=user)
            operators_after = list(scope_after.allowed_operators.order_by("name").values_list("name", flat=True))
            projects_after = list(scope_after.allowed_projects.order_by("name").values_list("name", flat=True))
            if (mode_before, operators_before, projects_before) != (scope_after.mode, operators_after, projects_after):
                AuditService.record(request=request, category="ADMINISTRATION", action="DATA_SCOPE_CHANGED", description="Escopo de dados alterado", obj=user, metadata={
                    "mode_before": mode_before, "mode_after": scope_after.mode,
                    "operators_before": operators_before, "operators_after": operators_after,
                    "projects_before": projects_before, "projects_after": projects_after,
                })
            if was_active != user.is_active:
                action = "USER_ACTIVATED" if user.is_active else "USER_DEACTIVATED"
                AuditService.record(request=request, category="ADMINISTRATION", action=action, description="Conta de usuário ativada" if user.is_active else "Conta de usuário desativada", obj=user)
            messages.success(request, "Acesso do usuário atualizado.")
            return redirect("configuracoes:user-detail", pk=user.pk)
    return render(request, "configuracoes/admin/user_form.html", _admin_context(request, "users", form=form, page_title="Editar usuário", user_object=user))


@login_required
@access_required("manage_groups")
def group_list(request):
    groups = Group.objects.annotate(member_count=Count("user", distinct=True)).order_by("name")
    return render(request, "configuracoes/admin/groups.html", _admin_context(request, "groups", groups=groups))


@login_required
@access_required("manage_groups")
def group_edit(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else None
    form = AccessGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        permissions_before = sorted(group.permissions.filter(content_type__app_label="configuracoes", codename__in=ADMIN_PERMISSIONS + ("view_dashboard", "view_cockpit", "save_analytics_views", "view_map", "view_rankings", "view_base", "view_ari", "import_cmdb", "export_base")).values_list("codename", flat=True)) if group else []
        selected = set(form.cleaned_data["permissions"].values_list("codename", flat=True))
        if group and len(_active_system_admins()) <= 1 and group.name == GROUP_SYSTEM_ADMIN and not set(ADMIN_PERMISSIONS).issubset(selected):
            form.add_error(None, "Mantenha as permissões administrativas do último perfil de sistema ativo.")
        if not form.errors:
            with transaction.atomic():
                saved = form.save()
            permissions_after = sorted(saved.permissions.filter(content_type__app_label="configuracoes", codename__in=ADMIN_PERMISSIONS + ("view_dashboard", "view_cockpit", "save_analytics_views", "view_map", "view_rankings", "view_base", "view_ari", "import_cmdb", "export_base")).values_list("codename", flat=True))
            if group and permissions_before != permissions_after:
                AuditService.record(request=request, category="ADMINISTRATION", action="PERMISSIONS_CHANGED", description="Permissões do grupo alteradas", obj=saved, metadata={"group": saved.name, "permissions_before": permissions_before, "permissions_after": permissions_after})
            messages.success(request, "Perfil de acesso salvo.")
            return redirect("configuracoes:group-edit", pk=saved.pk)
    return render(request, "configuracoes/admin/group_form.html", _admin_context(request, "groups", form=form, group=group, permission_groups=form.grouped_permissions()))


@login_required
@access_required("manage_data_scopes")
def scope_list(request):
    query = request.GET.get("q", "").strip()
    users = get_user_model().objects.filter(is_active=True).prefetch_related("groups", "data_scope__allowed_operators", "data_scope__allowed_projects")
    if query:
        users = users.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query))
    page_obj = Paginator(users.order_by("username"), 25).get_page(request.GET.get("page"))
    return render(request, "configuracoes/admin/scopes.html", _admin_context(request, "scopes", page_obj=page_obj, query=query))


@login_required
@access_required("manage_data_scopes")
def scope_edit(request, pk):
    user = get_object_or_404(get_user_model(), pk=pk)
    if user.is_superuser:
        messages.info(request, "Superusers possuem escopo global técnico implícito.")
        return redirect("configuracoes:scopes")
    scope, _ = UserDataScope.objects.get_or_create(user=user)
    mode_before = scope.mode
    operators_before = list(scope.allowed_operators.order_by("name").values_list("name", flat=True))
    projects_before = list(scope.allowed_projects.order_by("name").values_list("name", flat=True))
    form = UserDataScopeForm(request.POST or None, instance=scope)
    if request.method == "POST" and form.is_valid():
        form.save()
        operators_after = list(scope.allowed_operators.order_by("name").values_list("name", flat=True))
        projects_after = list(scope.allowed_projects.order_by("name").values_list("name", flat=True))
        if (mode_before, operators_before, projects_before) != (scope.mode, operators_after, projects_after):
            AuditService.record(request=request, category="ADMINISTRATION", action="DATA_SCOPE_CHANGED", description="Escopo de dados alterado", obj=user, metadata={
                "mode_before": mode_before, "mode_after": scope.mode,
                "operators_before": operators_before, "operators_after": operators_after,
                "projects_before": projects_before, "projects_after": projects_after,
            })
        messages.success(request, "Escopo de dados atualizado.")
        return redirect("configuracoes:scope-edit", pk=user.pk)
    return render(request, "configuracoes/admin/scope_form.html", _admin_context(request, "scopes", form=form, user_object=user))


@login_required
@access_required("view_audit_log")
def audit_list(request):
    events = AuditEvent.objects.select_related("user").all()
    filters = {key: request.GET.get(key, "").strip() for key in ("user", "category", "action", "result", "module", "from", "to", "q", "period", "page_size", "order")}
    if filters["user"].isdigit():
        events = events.filter(user_id=int(filters["user"]))
    if filters["category"]:
        events = events.filter(category=filters["category"])
    if filters["action"]:
        events = events.filter(action=filters["action"])
    if filters["result"] in ("SUCCESS", "FAILED", "BLOCKED"):
        events = events.filter(result=filters["result"])
    if filters["module"]:
        events = events.filter(module=filters["module"])
    now = timezone.now()
    period_start = {"today": timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0), "24h": now - timedelta(hours=24), "7d": now - timedelta(days=7), "30d": now - timedelta(days=30)}.get(filters["period"])
    if period_start:
        events = events.filter(timestamp__gte=period_start)
    date_field = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    try:
        date_from = date_field.clean(filters["from"]) if filters["from"] else None
        date_to = date_field.clean(filters["to"]) if filters["to"] else None
    except ValidationError:
        date_from = date_to = None
    if date_from:
        events = events.filter(timestamp__date__gte=date_from)
    if date_to:
        events = events.filter(timestamp__date__lte=date_to)
    query = filters["q"]
    if query:
        events = events.filter(Q(description__icontains=query) | Q(action__icontains=query) | Q(object_type__icontains=query) | Q(object_id__icontains=query) | Q(object_label__icontains=query) | Q(module__icontains=query) | Q(user__username__icontains=query) | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query))
    events = events.order_by("timestamp", "pk") if filters["order"] == "oldest" else events.order_by("-timestamp", "-pk")
    if request.GET.get("export") == "csv":
        rows = list(events)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(("Data", "Usu?rio", "Categoria", "A??o", "Resultado", "Objeto", "Descri??o", "IP"))
        def safe(value):
            value = str(value or "")
            return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
        for event in rows:
            writer.writerow(tuple(safe(value) for value in (event.timestamp.strftime("%d/%m/%Y %H:%M:%S"), event.user.get_username() if event.user else "Sistema", event.category, event.action, event.result, event.object_label or " ".join(filter(None, (event.object_type, event.object_id))), event.description, event.ip_address or "")))
        AuditService.record(request=request, category="EXPORT", action="AUDIT_EXPORT", module="Auditoria", description="Exporta??o do hist?rico de auditoria", metadata={"format": "csv", "rows": len(rows), "filters": {key: filters[key] for key in ("user", "category", "action", "result", "module", "from", "to", "period") if filters[key]}})
        return response
    filters["users"] = get_user_model().objects.filter(auditevent__isnull=False).distinct().order_by("username")
    labels = {"AUTHENTICATION": "Autentica??o", "ADMINISTRATION": "Administra??o", "INTEGRATION": "Integra??o", "EXPORT": "Exporta??o", "ANALYTICS": "Analytics", "COCKPIT": "Cockpit", "ACCOUNT": "Conta", "ARI": "ARI"}
    filters["categories"] = [(value, labels.get(value, value.title())) for value in AuditEvent.objects.order_by("category").values_list("category", flat=True).distinct()]
    filters["actions"] = AuditEvent.objects.order_by("action").values_list("action", flat=True).distinct()
    filters["modules"] = AuditEvent.objects.exclude(module="").order_by("module").values_list("module", flat=True).distinct()
    filters["page_sizes"] = (25, 50, 100)
    page_size = int(filters["page_size"]) if filters["page_size"].isdigit() and int(filters["page_size"]) in (25, 50, 100) else 50
    page_query = request.GET.copy()
    page_query.pop("page", None)
    page_query.pop("export", None)
    page_obj = Paginator(events, page_size).get_page(request.GET.get("page"))
    for event in page_obj.object_list:
        event.category_label = dict(filters["categories"]).get(event.category, event.category.title())
    context = _admin_context(request, "audit", page_obj=page_obj, filters=filters, page_query=page_query.urlencode(), total_events=events.count(), failures=events.filter(result="FAILED").count(), admin_actions=events.filter(category="ADMINISTRATION").count(), exports=events.filter(category="EXPORT").count())
    return render(request, "configuracoes/admin/audit.html", context)


@login_required
@access_required("view_audit_log")
def audit_detail(request, pk):
    event = get_object_or_404(AuditEvent.objects.select_related("user"), pk=pk)
    changes = []
    metadata = event.metadata or {}
    if isinstance(metadata.get("before"), dict) and isinstance(metadata.get("after"), dict):
        for key in sorted(set(metadata["before"]) | set(metadata["after"])):
            if metadata["before"].get(key) != metadata["after"].get(key):
                changes.append((key.replace("_", " ").title(), metadata["before"].get(key), metadata["after"].get(key)))
    elif isinstance(metadata, dict):
        for key, value in metadata.items():
            if key.endswith("_before"):
                after_key = key[:-7] + "_after"
                if after_key in metadata:
                    changes.append((key[:-7].replace("_", " ").title(), value, metadata[after_key]))
    technical_metadata = json.dumps(metadata, ensure_ascii=False, indent=2) if metadata else ""
    return render(request, "configuracoes/admin/audit_detail.html", _admin_context(request, "audit", event=event, changes=changes, technical_metadata=technical_metadata))


@login_required
@access_required("view_integrations")
def integrations(request):
    latest = CMDBImport.objects.order_by("-created_at").first()
    return render(request, "configuracoes/admin/integrations.html", _admin_context(request, "integrations", latest_import=latest, cmdb_count=CMDBLink.objects.filter(is_present_in_latest_import=True).count(), mapbox_configured=bool(settings.MAPBOX_PUBLIC_TOKEN)))


@login_required
@access_required("view_system_info")
def system_info(request):
    return render(request, "configuracoes/admin/system.html", _admin_context(request, "system", db_engine=connections["default"].vendor, timezone=settings.TIME_ZONE, environment="Desenvolvimento" if settings.DEBUG else "Produção", mapbox_configured=bool(settings.MAPBOX_PUBLIC_TOKEN)))


@login_required
@require_GET
def preferences(request):
    preference, _ = UserPreference.objects.get_or_create(user=request.user)
    return JsonResponse({"theme": preference.theme})


@login_required
@require_POST
def update_theme(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Corpo JSON inválido."}, status=400)
    if not isinstance(payload, dict) or payload.get("theme") not in UserPreference.Theme.values:
        return JsonResponse({"error": "Tema inválido. Use 'dark' ou 'light'."}, status=400)

    preference, _ = UserPreference.objects.get_or_create(user=request.user)
    preference.theme = payload["theme"]
    preference.save(update_fields=("theme", "updated_at"))
    return JsonResponse({"theme": preference.theme})
