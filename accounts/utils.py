from contextlib import contextmanager

from crum import get_current_user
from django.conf import settings

import threading

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
