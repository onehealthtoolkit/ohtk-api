from typing import Union
from django.db import models
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
            message=f"duplicate ${name}",
        )
    return None
