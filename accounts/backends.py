from graphql_jwt.backends import JSONWebTokenBackend
from graphql_jwt.exceptions import JSONWebTokenExpired
from oauth2_provider.oauth2_validators import OAuth2Validator


class MyJSONWebTokenBackend(JSONWebTokenBackend):
    def authenticate(self, request=None, **kwargs):
        try:
            return super().authenticate(request, **kwargs)
        except JSONWebTokenExpired:
            return None


class CustomOAuth2Validator(OAuth2Validator):
    def get_additional_claims(self, request):
        return {
            "username": request.user.username,
            "user_id": request.user.id,
            "email": request.user.email,
        }

    def get_userinfo_claims(self, request):
        claims = super().get_userinfo_claims(request)
        user = request.user
        claims["sub"] = user.id
        claims["username"] = user.username
        claims["user_id"] = user.id
        claims["email"] = user.email
        claims["first_name"] = user.first_name
        claims["last_name"] = user.last_name
        claims["is_staff"] = user.is_staff
        claims["is_superuser"] = user.is_superuser

        if user.is_authority_user:
            authority = user.authorityuser.authority
            ids = [a.id for a in authority.all_inherits_up()]
            claims["ids"] = str.join(".", [str(id) for id in reversed(ids)])

        return claims
