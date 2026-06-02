class IntegrationError(Exception):
    pass


class PublicSchemaDenied(IntegrationError):
    pass


class IntegrationClientDenied(IntegrationError):
    pass


class IntegrationScopeDenied(IntegrationError):
    pass


class IntegrationIdempotencyConflict(IntegrationError):
    pass


class WebhookSigningSecretError(IntegrationError):
    pass
