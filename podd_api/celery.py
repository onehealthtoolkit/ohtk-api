import os

from celery import Celery
from django.conf import settings
from tenant_schemas_celery.app import CeleryApp as TenantAwareCeleryApp


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "podd_api.settings")

app = TenantAwareCeleryApp("podd-api")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
