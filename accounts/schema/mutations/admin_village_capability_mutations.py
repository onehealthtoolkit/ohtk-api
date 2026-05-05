import graphene
from graphql_jwt.decorators import login_required, superuser_required

from accounts.village_capability import set_village_capability_enabled


class AdminVillageCapabilityUpdateMutation(graphene.Mutation):
    class Arguments:
        enabled = graphene.Boolean(required=True)

    enabled = graphene.Boolean(required=True)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, enabled):
        set_village_capability_enabled(enabled)
        return AdminVillageCapabilityUpdateMutation(enabled=enabled)
