import graphene
from django.conf import settings
from graphql import GraphQLError
from graphql_jwt.refresh_token.shortcuts import create_refresh_token
from graphql_jwt.shortcuts import get_token

from accounts.models import InvitationCode, AuthorityUser, VillageReporterAssignment
from accounts.schema.types import UserProfileType
from accounts.village_capability import is_village_capability_enabled


def _normalize_gender(gender):
    if gender is None or gender == "":
        return None
    valid = {choice for choice, _ in AuthorityUser.Gender.choices}
    if gender not in valid:
        raise GraphQLError(
            f"gender must be one of: {', '.join(sorted(valid))}"
        )
    return gender


def _normalize_age(age):
    if age is None:
        return None
    if age < 1 or age > 120:
        raise GraphQLError("age must be between 1 and 120")
    return age


class AuthorityUserRegisterMutation(graphene.Mutation):
    class Arguments:
        invitation_code = graphene.String(required=True)
        username = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        telephone = graphene.String(required=False)
        email = graphene.String(required=True)
        address = graphene.String(required=False)
        gender = graphene.String(required=False)
        age = graphene.Int(required=False)
        consent = graphene.Boolean(required=False)

    me = graphene.Field(UserProfileType)
    # return only when enable FEATURES.AUTO_LOGIN_AFTER_REGISTER
    token = graphene.String(required=False)
    refresh_token = graphene.String(required=False)

    @staticmethod
    def mutate(
        root,
        info,
        invitation_code,
        username,
        first_name,
        last_name,
        email,
        telephone=None,
        address=None,
        gender=None,
        age=None,
        consent=None,
    ):
        invitation = InvitationCode.objects.filter(code=invitation_code).first()
        if invitation:
            if AuthorityUser.objects.filter(username=username).exists():
                raise GraphQLError(f"username {username} already exist")
            normalized_gender = _normalize_gender(gender)
            normalized_age = _normalize_age(age)
            authority_user = AuthorityUser.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                telephone=telephone,
                email=email,
                address=address,
                gender=normalized_gender,
                age=normalized_age,
                consent=bool(consent),
                authority=invitation.authority,
                role=invitation.role,
            )
            if (
                authority_user.role == AuthorityUser.Role.REPORTER
                and is_village_capability_enabled()
            ):
                VillageReporterAssignment.objects.bulk_create(
                    [
                        VillageReporterAssignment(
                            reporter=authority_user, village=village
                        )
                        for village in invitation.villages.all()
                    ]
                )

            token = None
            refresh_token = None
            if settings.AUTO_LOGIN_AFTER_REGISTER:
                token = get_token(authority_user)
                refresh_token = create_refresh_token(authority_user)
                # delegate cookie setting to jwt_cookie that config at podd_api/urls.py
                info.context.jwt_token = token
                info.context.jwt_refresh_token = refresh_token

            return AuthorityUserRegisterMutation(
                me=authority_user, token=token, refresh_token=refresh_token
            )
        else:
            raise GraphQLError(f"invitation code {invitation_code} does not exist")
