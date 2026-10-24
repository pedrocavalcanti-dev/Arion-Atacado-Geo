from django import forms
from urllib.parse import urlsplit


class ArionDatabaseCandidateForm(forms.Form):
    host = forms.CharField(label="Host", max_length=255, initial="127.0.0.1")
    port = forms.IntegerField(label="Porta", min_value=1, max_value=65535, initial=3306)
    database = forms.CharField(label="Schema", max_length=128, initial="arion_geo")
    user = forms.CharField(label="Usu\u00e1rio", max_length=255)
    password = forms.CharField(label="Senha", max_length=512, required=False, strip=False,
                               widget=forms.PasswordInput(render_value=False))
    timeout = forms.IntegerField(label="Timeout (segundos)", min_value=1, max_value=60, initial=10)

    def clean(self):
        cleaned = super().clean()
        for field in ("host", "database", "user"):
            value = cleaned.get(field)
            if value is not None:
                cleaned[field] = value.strip()
                if not cleaned[field]:
                    self.add_error(field, "Este campo é obrigatório para MySQL.")
        return cleaned


class CMDBConfigurationForm(forms.Form):
    base_url = forms.URLField(label="URL base", max_length=500, widget=forms.URLInput(attrs={"placeholder": "https://servidor/otrs/nph-genericinterface.pl/Webservice/"}))
    username = forms.CharField(label="Usuário", max_length=255, required=False)
    password = forms.CharField(label="Senha", max_length=512, required=False, strip=False, widget=forms.PasswordInput(render_value=False))
    timeout = forms.IntegerField(label="Timeout (segundos)", min_value=1, max_value=60, initial=15)
    verify_tls = forms.BooleanField(label="Verificar certificado TLS", required=False, initial=True)
    batch_size = forms.IntegerField(label="Itens por lote", min_value=1, max_value=100, initial=50)

    def clean_base_url(self):
        value = self.cleaned_data["base_url"].strip().rstrip("/")
        if "@" in value.split("://", 1)[-1].split("/", 1)[0]:
            raise forms.ValidationError("Não inclua usuário ou senha na URL.")
        parsed = urlsplit(value)
        if parsed.query or parsed.fragment:
            raise forms.ValidationError("A URL base não pode conter parâmetros ou fragmento.")
        return value


class OTRSConfigurationForm(forms.Form):
    host = forms.CharField(label="Host / IP", max_length=255)
    port = forms.IntegerField(label="Porta", min_value=1, max_value=65535, initial=3306)
    database = forms.CharField(label="Banco", max_length=128, required=False)
    username = forms.CharField(label="Usuário", max_length=255, required=False)
    password = forms.CharField(label="Senha", max_length=512, required=False, strip=False, widget=forms.PasswordInput(render_value=False))
    timeout = forms.IntegerField(label="Timeout (segundos)", min_value=1, max_value=60, initial=10)

    def clean_host(self):
        return self.cleaned_data["host"].strip()

    def clean_database(self):
        return self.cleaned_data["database"].strip()


class CMDBSearchForm(forms.Form):
    class_name = forms.CharField(label="Classe", max_length=120, required=False, widget=forms.TextInput(attrs={"list": "cmdb-class-options", "placeholder": "Selecione ou informe a classe exata"}))
    number = forms.CharField(label="Número", max_length=120, required=False)
    name = forms.CharField(label="Nome", max_length=180, required=False)
    cixml_data = forms.CharField(label="Filtro CIXMLData", max_length=180, required=False)
    limit = forms.IntegerField(label="Limite", min_value=1, max_value=100, initial=25)


class CMDBGetForm(forms.Form):
    config_item_ids = forms.CharField(label="ConfigItemID", max_length=5000, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Informe um ou mais IDs separados por vírgula ou espaço"}))

    def clean_config_item_ids(self):
        values = self.cleaned_data["config_item_ids"].replace("\n", " ").replace(",", " ").split()
        unique = list(dict.fromkeys(values))
        if not unique or len(unique) > 500:
            raise forms.ValidationError("Informe de 1 a 500 ConfigItemID.")
        return unique
