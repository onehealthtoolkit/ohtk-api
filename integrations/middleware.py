from django.http import JsonResponse

from integrations.exceptions import PublicSchemaDenied
from integrations.services import assert_integration_tenant_schema


class IntegrationTenantGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/integrations/"):
            try:
                assert_integration_tenant_schema()
            except PublicSchemaDenied as exc:
                return JsonResponse(
                    {
                        "error": {
                            "code": "tenant_denied",
                            "message": str(exc),
                        }
                    },
                    status=403,
                )

        return self.get_response(request)
