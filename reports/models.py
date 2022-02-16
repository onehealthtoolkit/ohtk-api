from django.db import models
import uuid

from accounts.models import BaseModel, Authority


class Category(BaseModel):
    class Meta:
        verbose_name_plural = "categories"

    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class ReportType(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    definition = models.JSONField()
    authorities = models.ManyToManyField(
        Authority,
        related_name="reportTypes",
    )

    @staticmethod
    def filter_by_authority(authority: Authority):
        return ReportType.objects.filter(authorities__in=authority.all_inherits_up())
