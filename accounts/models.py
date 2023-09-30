import os
from random import randint
from uuid import uuid4

from dateutil.relativedelta import *
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models
from django.utils.timezone import now
from easy_thumbnails.fields import ThumbnailerImageField

from common.models import BaseModel, BaseModelManager


class Authority(BaseModel):
    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Authorities"

    objects = BaseModelManager()
    objects_original = models.Manager()

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=512)
    inherits = models.ManyToManyField(
        "self", related_name="authority_inherits", symmetrical=False, blank=True
    )
    area = models.PolygonField(null=True, blank=True)
    boundary_connects = models.ManyToManyField(
        "self",
        related_name="authority_boundary_connects",
        symmetrical=False,
        blank=True,
    )

    def __str__(self):
        return self.name

    def all_inherits_up(self):
        """find all authority that this one inherits. (include self)"""
        return Authority.objects.raw(f"select * from inherit_authority_up({self.id})")

    def all_inherits_down(self):
        """find all child authority that has recursive inherit up to this.(include self)"""
        return Authority.objects.raw(f"select * from inherit_authority_down({self.id})")

    def inherits_down_shallow(self):
        return Authority.objects.raw(
            f"select from_authority_id as id from accounts_authority_inherits where to_authority_id={self.id}"
        )

    def is_in_inherits_down(self, ids):
        ids_str = ",".join([str(id) for id in ids])
        sql = f"""
            select id from inherit_authority_down({self.id}) where id in ({ids_str})
        """
        auth = Authority.objects.raw(sql)
        if len(auth) > 0:
            return True
        return False

    def update_boundary_connects(self, boundary_connect_ids):
        for current_connected_authority in self.boundary_connects.all():
            if current_connected_authority.id not in boundary_connect_ids:
                current_connected_authority.boundary_connects.remove(self)

        boundary_connect_authorities: list[Authority] = Authority.objects.filter(
            pk__in=boundary_connect_ids
        )

        for connected_authority in boundary_connect_authorities:
            connected_authority.boundary_connects.add(self)

        self.boundary_connects.set(boundary_connect_authorities)


def path_and_rename(path):
    def wrapper(instance, filename):
        ext = filename.split(".")[-1]
        # get filename
        filename = "{}.{}".format(uuid4().hex, ext)
        # return the whole path to the file
        return os.path.join(path, filename)

    return wrapper


class User(AbstractUser):
    avatar = ThumbnailerImageField(
        upload_to=path_and_rename("avatars"), null=True, blank=True
    )
    fcm_token = models.CharField(max_length=200, blank=True)

    @property
    def is_authority_user(self):
        return hasattr(self, "authorityuser")

    @property
    def authority_role(self):
        if self.is_authority_user:
            return self.authorityuser.role
        return None

    def is_authority_role_in(self, roles):
        if self.is_authority_user and self.authority_role in roles:
            return True
        return False


class AuthorityUser(User):
    class Role(models.TextChoices):
        REPORTER = "REP", "Reporter"
        OFFICER = "OFC", "Officer"
        ADMIN = "ADM", "Admin"

    class Meta:
        verbose_name = "Authority User"

    avatar_url = models.URLField(max_length=300, blank=True, null=True)
    thumbnail_avatar_url = models.URLField(max_length=300, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    authority = models.ForeignKey(
        Authority, related_name="users", on_delete=models.CASCADE
    )
    role = models.CharField(
        choices=Role.choices, max_length=3, blank=True, default=Role.REPORTER
    )
    consent = models.BooleanField(default=False)

    def __str__(self):
        return self.username

    def has_summary_view_permission_on(self, authority_id):
        authority = Authority.objects.get(pk=authority_id)
        sub_authorities = self.authority.all_inherits_down()
        return authority in sub_authorities


class InvitationCode(BaseModel):
    objects = BaseModelManager()

    authority = models.ForeignKey(
        Authority, related_name="invitations", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=10, unique=True)
    from_date = models.DateTimeField()
    through_date = models.DateTimeField()
    role = models.CharField(
        AuthorityUser.Role.choices,
        max_length=3,
        blank=True,
        default=AuthorityUser.Role.REPORTER,
    )

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
    objects = BaseModelManager()

    key = models.CharField(max_length=100, primary_key=True)
    value = models.CharField(max_length=100)


class PasswordResetToken(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=128)
    token_expiry = models.DateTimeField()


class Configuration(BaseModel):
    objects = BaseModelManager()

    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField()

    @staticmethod
    def get(key):
        try:
            return Configuration.objects.get(key=key).value
        except Configuration.DoesNotExist:
            return None


class Place(BaseModel):
    objects = BaseModelManager()
    name = models.CharField(max_length=200)
    authority = models.ForeignKey(
        Authority, on_delete=models.CASCADE, related_name="places"
    )
    location = models.PointField(null=True, blank=True)
    notification_to = models.TextField(blank=True)
