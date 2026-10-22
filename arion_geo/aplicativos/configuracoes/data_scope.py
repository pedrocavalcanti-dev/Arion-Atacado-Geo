from .models import UserDataScope


class DataScopeService:
    """Apply operator/project scope to a CMDB queryset before use."""

    @staticmethod
    def get_scope(user):
        if not user.is_authenticated or user.is_superuser:
            return None
        try:
            return user.data_scope
        except UserDataScope.DoesNotExist:
            return None

    @classmethod
    def is_global(cls, user):
        scope = cls.get_scope(user)
        return scope is None or scope.mode == UserDataScope.Mode.ALL

    @classmethod
    def allowed_operator_ids(cls, user):
        scope = cls.get_scope(user)
        return None if scope is None or scope.mode == UserDataScope.Mode.ALL else scope.allowed_operators.values_list("pk", flat=True)

    @classmethod
    def allowed_project_ids(cls, user):
        scope = cls.get_scope(user)
        return None if scope is None or scope.mode == UserDataScope.Mode.ALL else scope.allowed_projects.values_list("pk", flat=True)

    @classmethod
    def filter_queryset(cls, user, queryset):
        scope = cls.get_scope(user)
        if scope is None or scope.mode == UserDataScope.Mode.ALL:
            return queryset
        return queryset.filter(
            operadora_id__in=scope.allowed_operators.values_list("pk", flat=True),
            projeto_id__in=scope.allowed_projects.values_list("pk", flat=True),
        )
