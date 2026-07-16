import urllib.parse

import xlwt
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.views.decorators.http import require_GET

from accounts.models import AuthorityUser
from accounts.village_capability import is_village_capability_enabled
from census.animal_census_capability import is_animal_census_capability_enabled
from census.export import build_export_table
from census.models import CensusRoundOccurrence


def _authenticate_request_user(request):
    """
    Resolve the user for excel download requests.

    GraphQL sets JWT cookies; regular Django views do not run GraphQL middleware,
    so we authenticate from the request (cookie/header) when needed.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user

    user = authenticate(request=request)
    if user is not None:
        return user

    # Browser form GET downloads send the JWT cookie but may not hit GraphQL
    # middleware; resolve the cookie explicitly as a fallback.
    try:
        from graphql_jwt.settings import jwt_settings
        from graphql_jwt.shortcuts import get_user_by_token

        token = request.COOKIES.get(jwt_settings.JWT_COOKIE_NAME)
        if token:
            return get_user_by_token(token, request)
    except Exception:
        return None
    return None


def _auto_column_width(ws, col_num, value):
    text = "" if value is None else str(value)
    width = max(len(text) * 256, 2560)
    current = ws.col(col_num).width or 0
    if width > current:
        ws.col(col_num).width = min(width, 15000)


@require_GET
def export_census_round_xls(request):
    """
    Export a census round coverage sheet.

    Query params:
      - occurrenceId (required)
      - authorityId (optional drill-down inside the viewer's hierarchy)
    """
    if not (
        is_village_capability_enabled() and is_animal_census_capability_enabled()
    ):
        return HttpResponse("Animal census is not enabled.", status=403)

    user = _authenticate_request_user(request)
    if user is None or not user.is_authenticated:
        return HttpResponse("Authentication required.", status=401)

    if not (
        user.is_superuser
        or user.is_authority_role_in(
            [AuthorityUser.Role.ADMIN, AuthorityUser.Role.OFFICER]
        )
    ):
        return HttpResponse("Permission denied.", status=403)

    occurrence_id = request.GET.get("occurrenceId")
    if not occurrence_id:
        return HttpResponse("occurrenceId is required.", status=400)
    try:
        occurrence = CensusRoundOccurrence.objects.select_related(
            "definition", "target_authority"
        ).get(pk=int(occurrence_id))
    except (CensusRoundOccurrence.DoesNotExist, TypeError, ValueError):
        return HttpResponse("Census round occurrence does not exist.", status=404)

    authority_id = request.GET.get("authorityId") or None
    if authority_id is not None:
        try:
            authority_id = int(authority_id)
        except (TypeError, ValueError):
            return HttpResponse("authorityId is invalid.", status=400)

    table = build_export_table(occurrence, user, authority_id=authority_id)
    if table is None:
        return HttpResponse("Permission denied.", status=403)

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("coverage")
    header_style = xlwt.easyxf(
        "font: bold True;"
        "pattern: pattern solid, fore_color gray25;"
        "alignment: horizontal center, wrap True;"
    )
    title_style = xlwt.easyxf("font: bold True;")
    body_style = xlwt.XFStyle()

    last_col = max(len(table["headers"]) - 1, 0)
    ws.write_merge(0, 0, 0, last_col, table["title"], title_style)
    ws.write_merge(
        1,
        1,
        0,
        last_col,
        (
            f"Occurrence: {table['occurrence_key']}  |  "
            f"Submitted: {table['submitted_count']}  "
            f"Missing: {table['missing_count']}  "
            f"Late: {table['late_count']}  "
            f"Rows: {table['total_count']}"
        ),
        body_style,
    )
    scope = table["authority_name"] or "viewer hierarchy"
    ws.write_merge(
        2,
        2,
        0,
        last_col,
        f"Authority scope: {scope}",
        body_style,
    )
    ws.write_merge(
        3,
        3,
        0,
        last_col,
        (
            "Rows are villages. Authority L* columns are hierarchy "
            "(root to leaf). Metric columns are household and species counts."
        ),
        body_style,
    )

    row_num = 5
    for col_num, header in enumerate(table["headers"]):
        ws.write(row_num, col_num, header, header_style)
        _auto_column_width(ws, col_num, header)

    for data_row in table["rows"]:
        row_num += 1
        for col_num, value in enumerate(data_row):
            cell = "" if value is None else value
            ws.write(row_num, col_num, cell, body_style)
            _auto_column_width(ws, col_num, cell)

    response = HttpResponse(content_type="application/ms-excel")
    filename = f"census_round_{occurrence.occurrence_key}.xls"
    response["Content-Disposition"] = "attachment; filename=%s" % urllib.parse.quote(
        filename
    )
    wb.save(response)
    return response
