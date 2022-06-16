from typing import Union
from common.types import AdminFieldValidationProblem, AdminValidationProblem
from django.db import models


def isNotEmpty(
    name: str,
    message: str,
    problemClass: AdminFieldValidationProblem = AdminFieldValidationProblem,
) -> Union[AdminFieldValidationProblem, None]:
    if not str:
        return problemClass(name=name, message=message)
    return None


def isDupliate(
    name: str,
    value: str,
    entity: models.Model,
) -> Union[AdminFieldValidationProblem, None]:
    if found := entity.objects.filter(**{name: value}).exists():
        return AdminFieldValidationProblem(
            name=name,
            message=f"duplicate ${name}",
        )
    return None
