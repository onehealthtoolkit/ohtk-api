import graphene
from common.types import AdminFieldValidationProblem
from reports.models.category import Category

from reports.schema.types import AdminCategoryUpdateProblem, AdminCategoryUpdateResult


class AdminCategoryUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminCategoryUpdateResult)

    @staticmethod
    def mutate(root, info, id, name, ordering):
        category = Category.objects.get(pk=id)

        if not category:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=[], message="Object not found")
            )

        if category.name != name and Category.objects.filter(name=name).exists():
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="duplicate name"
                        )
                    ]
                )
            )

        category.name = name
        category.ordering = ordering
        category.save()
        return AdminCategoryUpdateMutation(result=category)
