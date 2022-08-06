import threading
from contextlib import contextmanager
from typing import Callable

from crum import get_current_user
from django.conf import settings
from django.core.exceptions import PermissionDenied
from graphql_jwt.utils import jwt_payload

from accounts.models import User, AuthorityUser

thread_local = threading.local()


@contextmanager
def domain(domain_id):
    previous = getattr(thread_local, "open_surveillance", None)
    set_domain_id(domain_id)
    try:
        yield
    finally:
        if previous:
            set_domain_id(previous["domain_id"])
        else:
            delattr(thread_local, "open_surveillance")


def set_domain_id(id):
    thread_local.open_surveillance = {"domain_id": id}


def get_current_domain_id():
    user = get_current_user()
    if user and hasattr(user, "domain"):
        return user.domain_id

    try:
        return thread_local.open_surveillance["domain_id"]
    except:
        if hasattr(settings, "CURRENT_DOMAIN_ID"):
            return settings.CURRENT_DOMAIN_ID

    return None


def custom_jwt_payload(user, context=None):
    payload = jwt_payload(user, context)
    if user.is_authority_user:
        authority_user = user.authorityuser
        payload["authority_id"] = authority_user.authority_id
    return payload


def is_staff(user: User):
    return user.is_staff


def is_superuser(user) -> bool:
    return user.is_superuser


def is_authority_user(user: User) -> bool:
    return user.is_authority_user


def is_officer_role(user: User) -> bool:
    return (
        user.is_authority_user and user.authorityuser.role == AuthorityUser.Role.OFFICER
    )


def fn_and(left_fn, right_fn) -> Callable[[User], bool]:
    return lambda user: left_fn(user) and right_fn(user)


def fn_or(left_fn, right_fn) -> Callable[[User], bool]:
    return lambda user: left_fn(user) or right_fn(user)


def check_permission_authority_must_be_the_same(user: User, authority_id):
    if user.authorityuser.authority_id != authority_id:
        raise PermissionDenied(f"p001: user: {user.id}, authority_id: {authority_id}")


def check_permission_on_inherits_down(user: User, authority_ids: list):
    if user.is_authority_user:
        if not user.authorityuser.authority.is_in_inherits_down(authority_ids):
            raise PermissionDenied(f"p002: user: {user.id}, ids: {authority_ids}")


def check_permission_on_inherits_up(user: User, authority_ids: list):
    if user.is_authority_user:
        if not user.authorityuser.authority.is_in_inherits_up(authority_ids):
            raise PermissionDenied(f"p003: user: {user.id}, ids: {authority_ids}")
