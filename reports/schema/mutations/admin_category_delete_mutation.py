import graphene
from graphql_jwt.decorators import login_required, superuser_required

from reports.models import Category


class AdminCategoryDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        category = Category.objects.get(pk=id)
        category.delete()
        return {"success": True}
