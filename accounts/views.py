from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from oauth2_provider.decorators import protected_resource
from django.db import connection


@protected_resource()
@login_required
def userinfo(request):
    user = request.user
    if user.is_authority_user:
        obj = user.authorityuser.authority
        authority = {
            "id": obj.id,
            "name": obj.name,
            "code": obj.code,
        }
    else:
        authority = None

    # get current tenant
    tenant = connection.get_tenant()

    # render json data
    return JsonResponse(
        {
            "id": user.id,
            "username": f"{tenant.name}_{user.username}",
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_superuser": user.is_superuser,
            "authority": authority,
        }
    )
