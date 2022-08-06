import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty
from reports.models.category import Category

from reports.schema.types import (
    AdminCategoryUpdateProblem,
    AdminCategoryUpdateResult,
    AdminCategoryUpdateSuccess,
)
from graphene_file_upload.scalars import Upload


class AdminCategoryUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        icon = Upload(
            required=False,
        )
        ordering = graphene.Int(required=True)
        clear_icon = graphene.Boolean(required=None)

    result = graphene.Field(AdminCategoryUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(root, info, id, name, ordering, icon, clear_icon):
        try:
            category = Category.objects.get(pk=id)
        except Category.DoesNotExist:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=[], message="Object not found")
            )

        problems = []

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if category.name != name:
            if duplicateProblem := is_duplicate("name", name, Category):
                problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=problems)
            )

        if clear_icon:
            category.icon = None
        if icon != None:
            category.icon = icon
        category.name = name
        category.ordering = ordering
        category.save()
        return AdminCategoryUpdateMutation(
            result=AdminCategoryUpdateSuccess(category=category)
        )
