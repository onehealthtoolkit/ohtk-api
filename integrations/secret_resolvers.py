import os
from dataclasses import dataclass

from django.conf import settings

from integrations.exceptions import WebhookSigningSecretError


@dataclass(frozen=True)
class ResolvedSigningSecret:
    value: str
    key_id: str
    version: int


class WebhookSigningSecretResolver:
    def resolve(self, endpoint):
        raise NotImplementedError


class SettingsWebhookSigningSecretResolver(WebhookSigningSecretResolver):
    """
    Narrow I3 resolver for tests/local config.

    Production should replace this with a secret-manager or encrypted-secret
    backend that returns the value for endpoint.active_signing_secret_ref.
    """

    def resolve(self, endpoint):
        secret_ref = endpoint.active_signing_secret_ref
        if not secret_ref:
            raise WebhookSigningSecretError(
                "Webhook endpoint has no active signing secret reference."
            )

        if secret_ref.startswith("env://"):
            env_name = secret_ref[len("env://") :]
            value = os.environ.get(env_name)
            if not value:
                raise WebhookSigningSecretError(
                    "Webhook signing secret environment variable is not configured."
                )
            return ResolvedSigningSecret(
                value=value,
                key_id=env_name,
                version=endpoint.active_signing_secret_version,
            )

        configured = getattr(settings, "INTEGRATION_WEBHOOK_SIGNING_SECRETS", {})
        entry = configured.get(secret_ref)
        if entry is None:
            raise WebhookSigningSecretError(
                "Webhook signing secret reference is not configured."
            )

        if isinstance(entry, dict):
            value = entry.get("value")
            key_id = entry.get("key_id") or secret_ref
            version = entry.get("version") or endpoint.active_signing_secret_version
        else:
            value = entry
            key_id = secret_ref
            version = endpoint.active_signing_secret_version

        if not value:
            raise WebhookSigningSecretError(
                "Webhook signing secret reference resolved to an empty value."
            )

        return ResolvedSigningSecret(value=value, key_id=key_id, version=version)
