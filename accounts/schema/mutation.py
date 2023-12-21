import graphene

from accounts.schema.mutations import (
    AuthorityUserRegisterMutation,
    AdminUserChangePasswordMutation,
    AdminUserUpdateProfileMutation,
    AdminUserUploadAvatarMutation,
    AdminAuthorityCreateMutation,
    AdminAuthorityUpdateMutation,
    AdminAuthorityDeleteMutation,
    AdminAuthorityUserCreateMutation,
    AdminAuthorityUserUpdateMutation,
    AdminAuthorityUserUpdatePasswordMutation,
    AdminAuthorityUserDeleteMutation,
    AdminInvitationCodeCreateMutation,
    AdminInvitationCodeUpdateMutation,
    AdminInvitationCodeDeleteMutation,
    ResetPasswordRequestMutation,
    ResetPasswordMutation,
    VerifyLoginQRTokenMutation,
    ConfirmConsentMutation,
    AdminPlaceCreateMutation,
    AdminPlaceUpdateMutation,
    AdminPlaceDeleteMutation,
    AdminConfigurationCreateMutation,
    AdminConfigurationUpdateMutation,
    AdminConfigurationDeleteMutation,
    RequestToDeleteMyAccountMutation,
)


class Mutation(graphene.ObjectType):
    authority_user_register = AuthorityUserRegisterMutation.Field()
    admin_user_change_password = AdminUserChangePasswordMutation.Field()
    admin_user_update_profile = AdminUserUpdateProfileMutation.Field()
    admin_user_upload_avatar = AdminUserUploadAvatarMutation.Field()
    admin_authority_create = AdminAuthorityCreateMutation.Field()
    admin_authority_update = AdminAuthorityUpdateMutation.Field()
    admin_authority_delete = AdminAuthorityDeleteMutation.Field()
    admin_authority_user_create = AdminAuthorityUserCreateMutation.Field()
    admin_authority_user_update = AdminAuthorityUserUpdateMutation.Field()
    admin_authority_user_update_password = (
        AdminAuthorityUserUpdatePasswordMutation.Field()
    )
    admin_authority_user_delete = AdminAuthorityUserDeleteMutation.Field()
    admin_invitation_code_create = AdminInvitationCodeCreateMutation.Field()
    admin_invitation_code_update = AdminInvitationCodeUpdateMutation.Field()
    admin_invitation_code_delete = AdminInvitationCodeDeleteMutation.Field()
    reset_password_request = ResetPasswordRequestMutation.Field()
    reset_password = ResetPasswordMutation.Field()
    verify_login_qr_token = VerifyLoginQRTokenMutation.Field()
    confirm_consent = ConfirmConsentMutation.Field()
    admin_place_create = AdminPlaceCreateMutation.Field()
    admin_place_update = AdminPlaceUpdateMutation.Field()
    admin_place_delete = AdminPlaceDeleteMutation.Field()
    admin_configuration_create = AdminConfigurationCreateMutation.Field()
    admin_configuration_update = AdminConfigurationUpdateMutation.Field()
    admin_configuration_delete = AdminConfigurationDeleteMutation.Field()
    request_to_delete_my_account = RequestToDeleteMyAccountMutation.Field()
