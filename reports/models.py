from django.db import models
import uuid

from accounts.models import BaseModel, Authority


class Category(BaseModel):
    class Meta:
        verbose_name_plural = "categories"

    name = models.CharField(max_length=255, unique=True)


class ReportType(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    definition = models.JSONField()
    authorities = models.ManyToManyField(
        Authority,
        related_name="reportTypes",
    )
