import graphene
from django.contrib.gis.geos import Point
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, superuser_required

from accounts.models import Authority, AuthorityUser, Place
from accounts.utils import (
    check_permission_on_inherits_down,
    check_permission_authority_must_be_the_same,
)
from accounts.schema.types import (
    AdminPlaceCreateResult,
    AdminPlaceCreateProblem,
    AdminPlaceUpdateResult,
    AdminPlaceUpdateProblem,
    AdminPlaceUpdateSuccess,
)
from common.types import AdminFieldValidationProblem


class AdminPlaceCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        longitude = graphene.Float(required=True)
        latitude = graphene.Float(required=True)
        notification_to = graphene.String(required=False, default_value="")

    result = graphene.Field(AdminPlaceCreateResult)

    @staticmethod
    @login_required
    def mutate(root, info, name, authority_id, longitude, latitude, notification_to):
        problems = []

        if not Authority.objects.filter(pk=authority_id).exists():
            problems.append(
                AdminFieldValidationProblem(
                    name="authority_id", message="authority_id does not exist"
                )
            )

        # check if that authority is under user's authority
        user = info.context.user
        if user.is_authority_user:
            user_authority = info.context.user.authorityuser.authority
            if not user_authority.is_in_inherits_down([authority_id]):
                problems.append(
                    AdminFieldValidationProblem(
                        name="authority_id", message="authority_id is not in inherits"
                    )
                )

        if len(problems) > 0:
            return AdminPlaceCreateMutation(
                result=AdminPlaceCreateProblem(fields=problems)
            )

        # create place
        location = Point(longitude, latitude)
        place = Place.objects.create(
            name=name,
            authority_id=authority_id,
            location=location,
            notification_to=notification_to,
        )

        return AdminPlaceCreateMutation(result=place)


class AdminPlaceUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        longitude = graphene.Float(required=True)
        latitude = graphene.Float(required=True)
        notification_to = graphene.String(required=False, default_value="")

    result = graphene.Field(AdminPlaceUpdateResult)

    @staticmethod
    @login_required
    def mutate(
        root, info, id, name, authority_id, longitude, latitude, notification_to
    ):
        try:
            update_place = Place.objects.get(pk=id)
        except Place.DoesNotExist:
            return AdminPlaceUpdateMutation(
                result=AdminPlaceUpdateProblem(field=[], message="place does not exist")
            )
        user = info.context.user

        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(user, [update_place.authority_id])
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, update_place.authority_id
                )
            else:
                raise GraphQLError("You don't have permission to update place")

        update_place.name = name
        update_place.authority_id = authority_id
        update_place.location = Point(longitude, latitude)
        update_place.notification_to = notification_to
        update_place.save()
        return AdminPlaceUpdateMutation(result=update_place)


class AdminPlaceDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        place = Place.objects.get(pk=id)
        place.delete()
        return {"success": True}
