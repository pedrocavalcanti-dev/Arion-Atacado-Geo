from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError

from aplicativos.base_links.models import Operadora, Projeto
from .access_control import ALL_ACCESS_PERMISSIONS, PERMISSION_LABELS
from .models import UserDataScope


class ScopedUserFieldsMixin:
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.none(), required=False, label="Grupos de acesso")
    scope_mode = forms.ChoiceField(choices=UserDataScope.Mode.choices, label="Escopo dos dados")
    allowed_operators = forms.ModelMultipleChoiceField(queryset=Operadora.objects.none(), required=False, label="Operadoras")
    allowed_projects = forms.ModelMultipleChoiceField(queryset=Projeto.objects.none(), required=False, label="Projetos")

    def configure_scope_fields(self, instance=None):
        self.fields.setdefault("groups", forms.ModelMultipleChoiceField(queryset=Group.objects.none(), required=False, label="Grupos de acesso"))
        self.fields.setdefault("scope_mode", forms.ChoiceField(choices=UserDataScope.Mode.choices, label="Escopo dos dados"))
        self.fields.setdefault("allowed_operators", forms.ModelMultipleChoiceField(queryset=Operadora.objects.none(), required=False, label="Operadoras"))
        self.fields.setdefault("allowed_projects", forms.ModelMultipleChoiceField(queryset=Projeto.objects.none(), required=False, label="Projetos"))
        self.fields["groups"].queryset = Group.objects.order_by("name")
        self.fields["groups"].widget = forms.CheckboxSelectMultiple(attrs={"class": "visual-choice-list"})
        self.fields["allowed_operators"].queryset = Operadora.objects.filter(active=True).order_by("name")
        self.fields["allowed_operators"].widget = forms.CheckboxSelectMultiple(attrs={"class": "visual-choice-list operator-choices"})
        self.fields["allowed_projects"].queryset = Projeto.objects.filter(active=True).order_by("name")
        self.fields["allowed_projects"].widget = forms.CheckboxSelectMultiple(attrs={"class": "visual-choice-list project-choices"})
        if instance and instance.pk:
            self.fields["groups"].initial = instance.groups.all()
            scope = getattr(instance, "data_scope", None)
            if scope:
                self.fields["scope_mode"].initial = scope.mode
                self.fields["allowed_operators"].initial = scope.allowed_operators.all()
                self.fields["allowed_projects"].initial = scope.allowed_projects.all()
            else:
                self.fields["scope_mode"].initial = UserDataScope.Mode.ALL
        else:
            analyst = Group.objects.filter(name="Analista NOC").first()
            if analyst:
                self.fields["groups"].initial = [analyst.pk]
            self.fields["scope_mode"].initial = UserDataScope.Mode.ALL

    def save_access(self, user):
        user.groups.set(self.cleaned_data["groups"])
        scope, _ = UserDataScope.objects.get_or_create(user=user)
        scope.mode = self.cleaned_data["scope_mode"]
        scope.save(update_fields=("mode", "updated_at"))
        if scope.mode == UserDataScope.Mode.CUSTOM:
            scope.allowed_operators.set(self.cleaned_data["allowed_operators"])
            scope.allowed_projects.set(self.cleaned_data["allowed_projects"])
        else:
            scope.allowed_operators.clear()
            scope.allowed_projects.clear()


class UserCreateForm(ScopedUserFieldsMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False, label="Nome")
    last_name = forms.CharField(max_length=150, required=False, label="Sobrenome")
    email = forms.EmailField(required=False, label="E-mail")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_scope_fields()
        self.fields["scope_mode"].widget.attrs["data-scope-mode"] = ""
        self.fields["is_active"].widget.attrs.update({"class": "switch-input"}) if "is_active" in self.fields else None

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_access(user)
        return user


class UserUpdateForm(ScopedUserFieldsMixin, forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "email", "is_active")
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "email": "E-mail", "is_active": "Conta ativa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_scope_fields(self.instance)
        self.fields["is_active"].widget.attrs["class"] = "switch-input"
        self.fields["scope_mode"].widget.attrs["data-scope-mode"] = ""

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_access(user)
        return user


class AccessGroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
        label="Permissões",
    )

    class Meta:
        model = Group
        fields = ("name",)
        labels = {"name": "Nome do perfil de acesso"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.managed_permissions = Permission.objects.filter(
            content_type__app_label="configuracoes", codename__in=ALL_ACCESS_PERMISSIONS,
        ).order_by("codename")
        self.fields["permissions"].queryset = self.managed_permissions
        if self.instance.pk:
            self.fields["permissions"].initial = self.instance.permissions.filter(pk__in=self.managed_permissions.values("pk"))

    def grouped_permissions(self):
        groups = {}
        selected_values = {str(value) for value in (self["permissions"].value() or [])}
        for permission in self.managed_permissions:
            module, label = PERMISSION_LABELS[permission.codename]
            groups.setdefault(module, []).append({"permission": permission, "label": label, "selected": str(permission.pk) in selected_values})
        return groups

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if self.instance.pk and self.instance.name == "Administrador do Sistema" and name != self.instance.name:
            raise ValidationError("O nome do perfil Administrador do Sistema é reservado.")
        return name

    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            managed_ids = self.managed_permissions.values_list("pk", flat=True)
            group.permissions.remove(*Permission.objects.filter(pk__in=managed_ids))
            group.permissions.add(*self.cleaned_data["permissions"])
        return group


class UserDataScopeForm(forms.ModelForm):
    class Meta:
        model = UserDataScope
        fields = ("mode", "allowed_operators", "allowed_projects")
        labels = {"mode": "Escopo dos dados", "allowed_operators": "Operadoras permitidas", "allowed_projects": "Projetos permitidos"}
        widgets = {"allowed_operators": forms.CheckboxSelectMultiple, "allowed_projects": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_operators"].queryset = Operadora.objects.filter(active=True).order_by("name")
        self.fields["allowed_projects"].queryset = Projeto.objects.filter(active=True).order_by("name")

    def save(self, commit=True):
        scope = super().save(commit=commit)
        if commit and scope.mode == UserDataScope.Mode.ALL:
            scope.allowed_operators.clear()
            scope.allowed_projects.clear()
        return scope
