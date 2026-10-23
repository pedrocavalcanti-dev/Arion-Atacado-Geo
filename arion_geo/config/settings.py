"""Settings for the Arion Atacado Geo Django project."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-change-before-deployment",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "aplicativos.autenticacao.apps.AutenticacaoConfig",
    "aplicativos.configuracoes.apps.ConfiguracoesConfig",
    "aplicativos.auditoria.apps.AuditoriaConfig",
    "aplicativos.integracoes.apps.IntegracoesConfig",
    "aplicativos.ari.apps.AriConfig",
    "aplicativos.painel.apps.PainelConfig",
    "aplicativos.mapa.apps.MapaConfig",
    "aplicativos.rankings.apps.RankingsConfig",
    "aplicativos.base_links.apps.BaseLinksConfig",
]

MIDDLEWARE = [
    "config.middleware.RequestErrorMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "aplicativos.configuracoes.context_processors.user_theme",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "autenticacao:login"
LOGIN_REDIRECT_URL = "painel:index"
LOGOUT_REDIRECT_URL = "autenticacao:login"
CSRF_FAILURE_VIEW = "config.errors.csrf_failure"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "arion_errors": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "arion_error_console": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "arion_errors",
        },
    },
    "loggers": {
        "django.request": {
            # Django logs exception tracebacks here. The shared error handlers
            # write a sanitized request record, so suppress raw exception data.
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
        "config.errors": {
            "handlers": ["arion_error_console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

MAPBOX_PUBLIC_TOKEN = os.getenv("MAPBOX_PUBLIC_TOKEN", "").strip()

# ARI uploads are private and are only served through owner-checked views.
MEDIA_ROOT = BASE_DIR / "private_media"
ARI_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

