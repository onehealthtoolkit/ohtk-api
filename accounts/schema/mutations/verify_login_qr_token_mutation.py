import graphene
from graphql_jwt.refresh_token.shortcuts import create_refresh_token
from graphql_jwt.shortcuts import get_token
from graphql_jwt.utils import jwt_decode

from accounts.models import AuthorityUser
from accounts.schema.types import UserProfileType


class VerifyLoginQRTokenMutation(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)

    me = graphene.Field(UserProfileType)
    # return only when enable FEATURES.AUTO_LOGIN_AFTER_REGISTER
    token = graphene.String(required=False)
    refresh_token = graphene.String(required=False)

    @staticmethod
    def mutate(root, info, token):
        # verify request token
        payload = jwt_decode(token)

        # get user from payload
        login_user = AuthorityUser.objects.get(username=payload["username"])

        # if token is valid, create token , refresh_token and return
        token = get_token(login_user)
        refresh_token = create_refresh_token(login_user)

        return {
            "token": token,
            "refresh_token": refresh_token,
            "me": login_user,
        }
