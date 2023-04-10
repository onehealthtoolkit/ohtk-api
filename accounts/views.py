from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from oauth2_provider.decorators import protected_resource


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

    # render json data
    return JsonResponse(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_superuser": user.is_superuser,
            "authority": authority,
        }
    )
