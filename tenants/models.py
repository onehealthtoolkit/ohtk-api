from django.db import models

# Create your models here.
from django_tenants.models import TenantMixin, DomainMixin

from common.models import BaseModel, BaseModelManager


class Client(TenantMixin):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None)

    auto_create_schema = True


class Domain(DomainMixin):
    pass


class ExternalDomain(BaseModel):
    objects = BaseModelManager()

    name = models.CharField(max_length=20)
    domain = models.CharField(max_length=200)
