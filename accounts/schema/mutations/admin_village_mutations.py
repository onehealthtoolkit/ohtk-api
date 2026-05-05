import graphene
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import Authority, AuthorityUser, Village
from accounts.schema.types import (
    AdminVillageCreateProblem,
    AdminVillageCreateResult,
    AdminVillageUpdateProblem,
    AdminVillageUpdateResult,
)
from accounts.utils import (
    check_permission_authority_must_be_the_same,
    check_permission_on_inherits_down,
)
from accounts.village_capability import is_village_capability_enabled
from common.types import AdminFieldValidationProblem


def build_location(longitude, latitude):
    if longitude is None and latitude is None:
        return None
    return Point(longitude, latitude)


def validate_village_capability(problems):
    if not is_village_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="village_enabled",
                message="village capability is not enabled",
            )
        )


def validate_authority(user, authority_id, problems):
    if not Authority.objects.filter(pk=authority_id).exists():
        problems.append(
            AdminFieldValidationProblem(
                name="authority_id", message="authority_id does not exist"
            )
        )
        return

    if not user.is_superuser:
        user_authority = user.authorityuser.authority
        if not user_authority.is_in_inherits_down([authority_id]):
            problems.append(
                AdminFieldValidationProblem(
                    name="authority_id",
                    message="authority_id is not in inherits",
                )
            )


def validate_location(longitude, latitude, problems):
    if (longitude is None) != (latitude is None):
        problems.append(
            AdminFieldValidationProblem(
                name="location",
                message="longitude and latitude must be provided together",
            )
        )


class AdminVillageCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        longitude = graphene.Float(required=False)
        latitude = graphene.Float(required=False)
        active = graphene.Boolean(required=False, default_value=True)

    result = graphene.Field(AdminVillageCreateResult)

    @staticmethod
    @login_required
    def mutate(
        root, info, code, name, authority_id, longitude=None, latitude=None, active=True
    ):
        user = info.context.user
        if not (
            user.is_superuser or user.is_authority_role_in([AuthorityUser.Role.ADMIN])
        ):
            raise GraphQLError("Permission denied.")

        problems = []
        validate_village_capability(problems)
        validate_authority(user, authority_id, problems)
        validate_location(longitude, latitude, problems)

        if Village.objects.filter(authority_id=authority_id, code=code).exists():
            problems.append(
                AdminFieldValidationProblem(
                    name="code",
                    message="village code already exists for authority",
                )
            )

        if len(problems) > 0:
            return AdminVillageCreateMutation(
                result=AdminVillageCreateProblem(fields=problems)
            )

        village = Village.objects.create(
            code=code,
            name=name,
            authority_id=authority_id,
            location=build_location(longitude, latitude),
            active=active,
        )

        return AdminVillageCreateMutation(result=village)


class AdminVillageUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        longitude = graphene.Float(required=False)
        latitude = graphene.Float(required=False)
        active = graphene.Boolean(required=True)

    result = graphene.Field(AdminVillageUpdateResult)

    @staticmethod
    @login_required
    def mutate(
        root, info, id, code, name, authority_id, longitude=None, latitude=None, active=True
    ):
        if not is_village_capability_enabled():
            return AdminVillageUpdateMutation(
                result=AdminVillageUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="village_enabled",
                            message="village capability is not enabled",
                        )
                    ]
                )
            )

        try:
            update_village = Village.objects.get(pk=id)
        except Village.DoesNotExist:
            return AdminVillageUpdateMutation(
                result=AdminVillageUpdateProblem(
                    fields=[],
                    message="village does not exist",
                )
            )

        user = info.context.user
        try:
            if not user.is_superuser:
                if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                    check_permission_on_inherits_down(user, [update_village.authority_id])
                    check_permission_on_inherits_down(user, [authority_id])
                elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                    check_permission_authority_must_be_the_same(
                        user, update_village.authority_id
                    )
                    check_permission_authority_must_be_the_same(user, authority_id)
                else:
                    raise GraphQLError("Permission denied.")
        except PermissionDenied:
            raise GraphQLError("Permission denied.")

        problems = []
        validate_authority(user, authority_id, problems)
        validate_location(longitude, latitude, problems)

        if (
            Village.objects.filter(authority_id=authority_id, code=code)
            .exclude(pk=id)
            .exists()
        ):
            problems.append(
                AdminFieldValidationProblem(
                    name="code",
                    message="village code already exists for authority",
                )
            )

        if len(problems) > 0:
            return AdminVillageUpdateMutation(
                result=AdminVillageUpdateProblem(fields=problems)
            )

        update_village.code = code
        update_village.name = name
        update_village.authority_id = authority_id
        update_village.location = build_location(longitude, latitude)
        update_village.active = active
        update_village.save()
        return AdminVillageUpdateMutation(result=update_village)
