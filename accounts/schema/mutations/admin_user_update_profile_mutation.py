import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser


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


class AdminUserUpdateProfileMutation(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        telephone = graphene.String(required=False)
        address = graphene.String(required=False)
        gender = graphene.String(required=False)
        age = graphene.Int(required=False)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        first_name,
        last_name,
        telephone=None,
        address=None,
        gender=None,
        age=None,
    ):
        user = info.context.user
        if user.is_authority_user:
            update_user = user.authorityuser
        else:
            update_user = user

        update_user.first_name = first_name
        update_user.last_name = last_name
        update_user.telephone = telephone
        update_user.address = address

        # Only authority users have gender/age columns (AuthorityUser).
        if user.is_authority_user:
            update_user.gender = _normalize_gender(gender)
            update_user.age = _normalize_age(age)

        update_user.save()
        return AdminUserUpdateProfileMutation(success=True)
