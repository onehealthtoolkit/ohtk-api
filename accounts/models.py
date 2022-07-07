from random import randint
from dateutil.relativedelta import *

from django.contrib.auth.models import UserManager, AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.timezone import now

from accounts.utils import get_current_domain_id


class BaseModel(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None)

    def delete(self, hard=False, **kwargs):
        if hard:
            super(BaseModel, self).delete()
        else:
            self.deleted_at = now()
            self.save()

    def restore(self):
        self.deleted_at = None
        self.save()


class Authority(BaseModel):
    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Authorities"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=512)
    inherits = models.ManyToManyField(
        "self", related_name="authority_inherits", symmetrical=False, blank=True
    )

    def __str__(self):
        return self.name

    def all_inherits_up(self):
        """find all authority that this one inherits. (include self)"""
        return Authority.objects.raw(f"select * from inherit_authority_up({self.id})")

    def all_inherits_down(self):
        """find all child authority that has recursive inherit up to this.(include self)"""
        return Authority.objects.raw(f"select * from inherit_authority_down({self.id})")


class User(AbstractUser):
    avatar = models.ImageField(upload_to="avatars", null=True, blank=True)

    def is_authority_user(self):
        return hasattr(self, "authorityuser")


class AuthorityUser(User):
    class Meta:
        verbose_name = "Authority User"

    avatar_url = models.URLField(max_length=300, blank=True, null=True)
    thumbnail_avatar_url = models.URLField(max_length=300, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    authority = models.ForeignKey(
        Authority, related_name="users", on_delete=models.CASCADE
    )

    def __str__(self):
        return self.username


class InvitationCode(BaseModel):
    authority = models.ForeignKey(
        Authority, related_name="inviations", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=10, unique=True)
    from_date = models.DateTimeField()
    through_date = models.DateTimeField()

    def __str__(self):
        return f"{self.code} {self.authority.name}"

    def save(self, *args, **kwargs):
        if not self.id:
            if self.code is None:
                self.code = self.generate_code()
            if self.from_date is None:
                self.from_date = now()
            if self.through_date is None:
                self.through_date = self.from_date + relativedelta(years=1)
        super(InvitationCode, self).save(*args, **kwargs)

    @staticmethod
    def generate_code():
        for i in range(10):
            code = "{0:07d}".format(randint(0, 9999999))
            if InvitationCode.objects.filter(code=code).count() == 0:
                return code
        raise Exception("could not generate code")


class Feature(BaseModel):
    key = models.CharField(max_length=100, primary_key=True)
    value = models.CharField(max_length=100)
