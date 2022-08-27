from typing import Union
from django.db import models
from django.http import parse_cookie
from graphql_jwt.utils import jwt_decode

from common.types import AdminFieldValidationProblem


def is_not_empty(
    name: str,
    value: str,
    message: str,
    problem_class: AdminFieldValidationProblem = AdminFieldValidationProblem,
) -> Union[AdminFieldValidationProblem, None]:
    if not value:
        return problem_class(name=name, message=message)
    return None


def is_duplicate(
    name: str,
    value: str,
    entity: models.Model,
) -> Union[AdminFieldValidationProblem, None]:
    if entity.objects.filter(**{name: value}).exists():
        return AdminFieldValidationProblem(
            name=name,
            message=f"duplicate {name}",
        )
    return None


def check_and_get(name: str, value: str, entity: models.Model):
    try:
        obj = entity.objects.get(pk=value)
        return obj, None
    except entity.DoesNotExist:
        return None, AdminFieldValidationProblem(
            name=camel(name),
            message=f"this field is required",
        )


def camel(snake_str):
    first, *others = snake_str.split("_")
    return "".join([first.lower(), *map(str.title, others)])


def extract_jwt_payload_from_asgi_scope(scope):
    username = None
    authority_id = None
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            cookies = parse_cookie(value.decode("latin1"))
            token = cookies["JWT"]
            payload = jwt_decode(token)
            username = payload["username"]
            authority_id = payload["authority_id"]
    return {
        "username": username,
        "authority_id": authority_id,
    }
