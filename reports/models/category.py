from django.contrib.gis.db import models

from accounts.models import BaseModel


class Category(BaseModel):
    class Meta:
        verbose_name_plural = "categories"

    name = models.CharField(max_length=255, unique=True)
    icon = models.ImageField(upload_to="icons", blank=True, null=True)
    ordering = models.IntegerField(default=0)

    def __str__(self):
        return self.name
