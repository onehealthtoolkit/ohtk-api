from django.http import JsonResponse

from tenants.models import Client, ExternalDomain


def tenants(request):
    clients = Client.objects.filter(deleted_at__isnull=True)
    results = []
    for client in clients:
        # Prefer the primary domain. domains.first() is ordered by PK and can
        # return an emulator/LAN alias (e.g. 10.0.2.2) added for mobile, which
        # breaks the Mac dashboard GraphQL host selection.
        domain = (
            client.domains.filter(is_primary=True).first()
            or client.domains.first()
        )
        if domain is None:
            continue
        results.append(
            {
                "label": client.name,
                "domain": domain.domain,
                "external": False,
            }
        )
    for ext in ExternalDomain.objects.all():
        results.append(
            {
                "label": ext.name,
                "domain": ext.domain,
                "external": True,
            }
        )
    return JsonResponse({"tenants": results})
