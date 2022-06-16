import graphene
from common.types import AdminFieldValidationProblem
from reports.models.category import Category

from reports.schema.types import AdminCategoryCreateProblem, AdminCategoryCreateResult


class AdminCategoryCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminCategoryCreateResult)

    @staticmethod
    def mutate(
        root,
        info,
        name,
        ordering,
    ):
        if Category.objects.filter(name=name).exists():
            return AdminCategoryCreateMutation(
                result=AdminCategoryCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="duplicate name"
                        )
                    ]
                )
            )

        if not name:
            return AdminCategoryCreateMutation(
                result=AdminCategoryCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="name must not be empty"
                        )
                    ]
                )
            )

        category = Category.objects.create(
            name=name,
            ordering=ordering,
        )
        return AdminCategoryCreateMutation(result=category)
