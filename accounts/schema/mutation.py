import graphene

from accounts.schema.mutations.admin_authority_mutations import (
    AdminAuthorityCreateMutation,
    AdminAuthorityUpdateMutation,
    AdminAuthorityDeleteMutation,
)
from accounts.schema.mutations.admin_authority_user_mutations import (
    AdminAuthorityUserCreateMutation,
    AdminAuthorityUserUpdateMutation,
    AdminAuthorityUserDeleteMutation,
)
from accounts.schema.mutations.admin_invitation_code_mutations import (
    AdminInvitationCodeCreateMutation,
    AdminInvitationCodeUpdateMutation,
    AdminInvitationCodeDeleteMutation,
)
from accounts.schema.mutations.admin_user_change_password_mutation import (
    AdminUserChangePasswordMutation,
)
from accounts.schema.mutations.admin_user_upload_avatar_mutation import (
    AdminUserUploadAvatarMutation,
)
from accounts.schema.mutations.authority_user_mutations import (
    AuthorityUserRegisterMutation,
)


class Mutation(graphene.ObjectType):
    authority_user_register = AuthorityUserRegisterMutation.Field()
    admin_user_change_password = AdminUserChangePasswordMutation.Field()
    admin_user_upload_avatar = AdminUserUploadAvatarMutation.Field()
    admin_authority_create = AdminAuthorityCreateMutation.Field()
    admin_authority_update = AdminAuthorityUpdateMutation.Field()
    admin_authority_delete = AdminAuthorityDeleteMutation.Field()
    admin_authority_user_create = AdminAuthorityUserCreateMutation.Field()
    admin_authority_user_update = AdminAuthorityUserUpdateMutation.Field()
    admin_authority_user_delete = AdminAuthorityUserDeleteMutation.Field()
    admin_invitation_code_create = AdminInvitationCodeCreateMutation.Field()
    admin_invitation_code_update = AdminInvitationCodeUpdateMutation.Field()
    admin_invitation_code_delete = AdminInvitationCodeDeleteMutation.Field()
