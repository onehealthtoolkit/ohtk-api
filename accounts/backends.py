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
        claims["sub"] = request.user.id
        claims["username"] = request.user.username
        claims["user_id"] = request.user.id
        claims["email"] = request.user.email
        claims["first_name"] = request.user.first_name
        claims["last_name"] = request.user.last_name
        return claims
