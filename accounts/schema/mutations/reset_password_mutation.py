import secrets
from datetime import timedelta

import graphene
from django.conf import settings
from django.core.mail import send_mail
from django.utils.timezone import now

from accounts.models import User, PasswordResetToken
from tenants.models import Domain, Client
from django.db import connection


class ResetPasswordRequestMutation(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)

    success = graphene.Boolean()

    @staticmethod
    def mutate(root, info, email):
        # get user by email
        try:
            user = User.objects.get(email=email)
            token = secrets.token_urlsafe(48)

            try:
                client = Client.objects.get(schema_name=connection.schema_name)
                domain_instance = Domain.objects.filter(tenant=client).first()
                if domain_instance:
                    domain = domain_instance.domain
            except Client.DoesNotExist:
                domain = None

            # save reset password token
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                token_expiry=now() + timedelta(hours=1),
            )

            link = f"{settings.DASHBOARD_URL}/reset-password/{token}"
            if domain:
                link = link + "?domain=" + domain

            if settings.DEBUG:
                print(f"Reset password link: {link}")
            else:
                send_mail(
                    "Reset password",
                    f"Please click the link to reset your password: {link}",
                    f"noreply@{settings.EMAIL_DOMAIN}",
                    [email],
                    fail_silently=False,
                )

        except User.DoesNotExist:
            pass
        # always return true
        return ResetPasswordMutation(success=True)


class ResetPasswordMutation(graphene.Mutation):
    class Arguments:
        token = graphene.String(required=True)
        password = graphene.String(required=True)

    success = graphene.Boolean()

    @staticmethod
    def mutate(root, info, token, password):
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
            reset_token.user.set_password(password)
            reset_token.user.save()
            reset_token.delete()
        except PasswordResetToken.DoesNotExist:
            pass
        # always return true
        return ResetPasswordMutation(success=True)
