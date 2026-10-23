from .models import GroupDataScope


class DataScopeService:
    """Resolve operational data access through a user's access group(s)."""

    @staticmethod
    def get_scope(user):
        if not user.is_authenticated or user.is_superuser:
            return None
        groups = list(user.groups.order_by("pk")[:2])
        if len(groups) != 1:
            return None
        try:
            return groups[0].data_scope
        except GroupDataScope.DoesNotExist:
            return None

    @classmethod
    def is_global(cls, user):
        if user.is_authenticated and user.is_superuser:
            return True
        scopes = cls._scopes_for_user(user)
        return bool(scopes) and all(scope.mode == GroupDataScope.Mode.ALL for scope in scopes)

    @classmethod
    def allowed_operator_ids(cls, user):
        scopes = cls._scopes_for_user(user)
        if user.is_authenticated and user.is_superuser:
            return None
        if not scopes:
            return ()
        custom = [scope for scope in scopes if scope.mode == GroupDataScope.Mode.CUSTOM]
        if not custom:
            return None
        ids = set(custom[0].allowed_operators.values_list("pk", flat=True))
        for scope in custom[1:]:
            ids.intersection_update(scope.allowed_operators.values_list("pk", flat=True))
        return ids

    @classmethod
    def allowed_project_ids(cls, user):
        scopes = cls._scopes_for_user(user)
        if user.is_authenticated and user.is_superuser:
            return None
        if not scopes:
            return ()
        custom = [scope for scope in scopes if scope.mode == GroupDataScope.Mode.CUSTOM]
        if not custom:
            return None
        ids = set(custom[0].allowed_projects.values_list("pk", flat=True))
        for scope in custom[1:]:
            ids.intersection_update(scope.allowed_projects.values_list("pk", flat=True))
        return ids

    @classmethod
    def filter_queryset(cls, user, queryset):
        if user.is_authenticated and user.is_superuser:
            return queryset
        scopes = cls._scopes_for_user(user)
        if not scopes:
            return queryset.none()
        model_label = queryset.model._meta.label_lower
        if model_label == "integracoes.cmdblinkmirror":
            for scope in scopes:
                if scope.mode != GroupDataScope.Mode.CUSTOM:
                    continue
                allowed_operator_names = scope.allowed_operators.values_list("name", flat=True)
                allowed_project_names = scope.allowed_projects.values_list("name", flat=True)
                queryset = queryset.filter(
                    operator__name__in=allowed_operator_names,
                    legacy_project__in=allowed_project_names,
                )
            return queryset
        for scope in scopes:
            if scope.mode == GroupDataScope.Mode.CUSTOM:
                queryset = queryset.filter(
                    operadora_id__in=scope.allowed_operators.values_list("pk", flat=True),
                    projeto_id__in=scope.allowed_projects.values_list("pk", flat=True),
                )
        return queryset

    @staticmethod
    def _scopes_for_user(user):
        if not user.is_authenticated or user.is_superuser:
            return []
        groups = user.groups.all().prefetch_related("data_scope__allowed_operators", "data_scope__allowed_projects")
        scopes = []
        for group in groups:
            try:
                scopes.append(group.data_scope)
            except GroupDataScope.DoesNotExist:
                # Missing configuration is always restrictive.
                return []
        return scopes
