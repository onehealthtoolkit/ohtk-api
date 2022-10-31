from django.http import JsonResponse

from tenants.models import Client


def tenants(request):
    clients = Client.objects.filter(deleted_at__isnull=True)
    results = []
    for client in clients:
        results.append(
            {
                "label": client.name,
                "domain": client.domains.first().domain,
            }
        )
    return JsonResponse({"tenants": results})
