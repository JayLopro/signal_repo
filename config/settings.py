"""
Django settings for config project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# APP_MODE 우선순위: 환경변수 → .env.<mode> → .env (fallback)
# - test: 로컬 개발 (LLM X)
# - staging: 로컬 LLM 검증 / PA 1차 배포 (LLM 호출은 ENABLE_LLM_ON_PA로 추가 차단)
# - production: 향후 운영
APP_MODE = os.getenv("APP_MODE", "test").lower()

_mode_env_file = BASE_DIR / f".env.{APP_MODE}"
if _mode_env_file.exists():
    load_dotenv(_mode_env_file, override=False)
load_dotenv(BASE_DIR / ".env", override=False)

# decisions.md §7 — PA 배포 시 반드시 false. 누락/true이더라도 LLM 호출 가드(C4)에서 차단.
ENABLE_LLM_ON_PA = os.getenv("ENABLE_LLM_ON_PA", "false").lower() == "true"


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-i%+_=t2*_$bx82t&4rju3*kng@y$zlxiiv9@4n(5_^q^=cy%ak",
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboard.context_processors.sidebar",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# 데이터마트 (읽기전용) — Phase 1에서 빌드. decisions.md §7
MART_DB_PATH = BASE_DIR / "data" / "sqlite3" / "suwon_4111.sqlite3"
ADMDONG_TOPOJSON_PATH = BASE_DIR / "data" / "수원시_background.json"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
