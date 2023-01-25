from django.http import JsonResponse

from tenants.models import Client, ExternalDomain


def tenants(request):
    clients = Client.objects.filter(deleted_at__isnull=True)
    results = []
    for client in clients:
        results.append(
            {
                "label": client.name,
                "domain": client.domains.first().domain,
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
