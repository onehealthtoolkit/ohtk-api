from graphql_jwt.backends import JSONWebTokenBackend
from graphql_jwt.exceptions import JSONWebTokenExpired


class MyJSONWebTokenBackend(JSONWebTokenBackend):
    def authenticate(self, request=None, **kwargs):
        try:
            super().authenticate(request, **kwargs)
        except JSONWebTokenExpired:
            return None
