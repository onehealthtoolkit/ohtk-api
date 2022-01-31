from contextlib import contextmanager

from crum import get_current_user
from django.conf import settings

import threading

from graphql_jwt.utils import jwt_payload

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
    if hasattr(user, "authorityuser"):
        authority_user = user.authorityuser
        payload["authority_id"] = authority_user.authority_id
    return payload
