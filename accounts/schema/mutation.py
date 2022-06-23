import graphene

from accounts.schema.admin_authority_mutations import (
    AdminAuthorityCreateMutation,
    AdminAuthorityUpdateMutation,
)
from accounts.schema.admin_authority_user_mutations import (
    AdminAuthorityUserCreateMutation,
    AdminAuthorityUserUpdateMutation,
)
from accounts.schema.admin_invitation_code_mutations import (
    AdminInvitationCodeCreateMutation,
    AdminInvitationCodeUpdateMutation,
)
from accounts.schema.authority_user_mutations import AuthorityUserRegisterMutation


class Mutation(graphene.ObjectType):
    authority_user_register = AuthorityUserRegisterMutation.Field()
    admin_authority_create = AdminAuthorityCreateMutation.Field()
    admin_authority_update = AdminAuthorityUpdateMutation.Field()
    admin_authority_user_create = AdminAuthorityUserCreateMutation.Field()
    admin_authority_user_update = AdminAuthorityUserUpdateMutation.Field()
    admin_invitation_code_create = AdminInvitationCodeCreateMutation.Field()
    admin_invitation_code_update = AdminInvitationCodeUpdateMutation.Field()
