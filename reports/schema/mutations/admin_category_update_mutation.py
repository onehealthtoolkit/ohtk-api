import graphene
from accounts.schema.utils import is_duplicate, is_not_empty
from common.types import AdminFieldValidationProblem
from reports.models.category import Category

from reports.schema.types import (
    AdminCategoryUpdateProblem,
    AdminCategoryUpdateResult,
    AdminCategoryUpdateSuccess,
)


class AdminCategoryUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminCategoryUpdateResult)

    @staticmethod
    def mutate(root, info, id, name, ordering):
        try:
            category = Category.objects.get(pk=id)
        except Category.DoesNotExist:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=[], message="Object not found")
            )

        problems = []

        if name_problem := is_not_empty("name", "Name must not be empty"):
            problems.append(name_problem)

        if category.name != name:
            if duplicateProblem := is_duplicate("name", name, Category):
                problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=problems)
            )

        category.name = name
        category.ordering = ordering
        category.save()
        return AdminCategoryUpdateMutation(
            result=AdminCategoryUpdateSuccess(category=category)
        )
