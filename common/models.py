from django.contrib.gis.db import models
from django.utils.timezone import now


class BaseModel(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None)

    def delete(self, hard=False, **kwargs):
        if hard:
            super().delete()
        else:
            self.deleted_at = now()
            self.save(update_fields=("deleted_at",))

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=("deleted_at",))


class BaseModelManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
