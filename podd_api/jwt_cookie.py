from functools import wraps

from django.utils import timezone
from graphql_jwt.settings import jwt_settings
from graphql_jwt.utils import set_cookie


def delete_cookie(response, key):
    kwargs = {
        "path": jwt_settings.JWT_COOKIE_PATH,
        "domain": jwt_settings.JWT_COOKIE_DOMAIN,
        "samesite": jwt_settings.JWT_COOKIE_SAMESITE,
    }
    response.delete_cookie(key, **kwargs)


def jwt_cookie(view_func):
    # Keep SameSite on cookie deletion until the auth surface moves off django-graphql-jwt.
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        request.jwt_cookie = True
        response = view_func(request, *args, **kwargs)

        if hasattr(request, "jwt_token"):
            expires = timezone.now() + jwt_settings.JWT_EXPIRATION_DELTA
            set_cookie(
                response,
                jwt_settings.JWT_COOKIE_NAME,
                request.jwt_token,
                expires=expires,
            )

            if hasattr(request, "jwt_refresh_token"):
                refresh_token = request.jwt_refresh_token
                expires = (
                    refresh_token.created + jwt_settings.JWT_REFRESH_EXPIRATION_DELTA
                )
                set_cookie(
                    response,
                    jwt_settings.JWT_REFRESH_TOKEN_COOKIE_NAME,
                    refresh_token.token,
                    expires=expires,
                )

        if hasattr(request, "delete_jwt_cookie"):
            delete_cookie(response, jwt_settings.JWT_COOKIE_NAME)

        if hasattr(request, "delete_refresh_token_cookie"):
            delete_cookie(response, jwt_settings.JWT_REFRESH_TOKEN_COOKIE_NAME)

        return response

    return wrapped_view
