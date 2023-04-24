from django.http import HttpResponse
from accounts.models import Authority, AuthorityUser
import xlwt
from django.utils.dateparse import parse_datetime
from reports.models.report import IncidentReport, ZeroReport
from django.db.models import Count, OuterRef, Subquery, Func

# Create your views here.


def export_inactive_reporter_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date = parse_datetime(request.GET.get("fromDate"))
    to_date = parse_datetime(request.GET.get("toDate"))

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="inactive_reporter.xls"'

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Inactive Reporter")

    # Sheet header, first row
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    row_num = write_header(
        row_num, 0, 4, ws, "Inactive Reporter", from_date, to_date, authority
    )
    columns = [
        "Username",
        "First Name",
        "Last Name",
        "Telephone",
        "Authority Name",
    ]

    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)  # at 0 row 0 column

    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()

    exclude = (
        IncidentReport.objects.all()
        .filter(relevant_authorities__in=sub_authorities, test_flag=False)
        .values_list("reported_by__id")
    )
    if from_date:
        exclude = exclude.filter(created_at__gte=from_date)

    if to_date:
        exclude = exclude.filter(created_at__lte=to_date)

    rows = (
        AuthorityUser.objects.exclude(id__in=exclude)
        .annotate(Count("username"))
        .order_by("username")
        .filter(authority__in=sub_authorities)
        .values("username", "first_name", "last_name", "telephone", "authority__name")
    )

    # print(rows.query)
    for row in rows:
        row_num += 1
        col_num = 0
        for item in row:
            cwidth = ws.col(col_num).width
            if (len(row[item]) * 367) > cwidth:
                ws.col(col_num).width = (
                    len(row[item]) * 367
                )  # (Modify column width to match biggest data in that column)
            ws.write(row_num, col_num, row[item], font_style)
            col_num += 1

    wb.save(response)

    return response
    # return HttpResponse("return this string")


def export_reporter_performance_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date = parse_datetime(request.GET.get("fromDate"))
    to_date = parse_datetime(request.GET.get("toDate"))

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="reporter_performance.xls"'

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Reporter Performance")

    # Sheet header, first row
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    row_num = write_header(
        row_num, 0, 6, ws, "Inactive Reporter", from_date, to_date, authority
    )

    columns = [
        "Username",
        "First Name",
        "Last Name",
        "Telephone",
        "Authority Name",
        "Zero Report",
        "Incident Report",
    ]

    for col_num in range(len(columns)):
        cwidth = ws.col(col_num).width
        if (len(columns[col_num]) * 367) > cwidth:
            ws.col(col_num).width = (
                len(columns[col_num]) * 367
            )  # (Modify column width to match biggest data in that column)

        ws.write(row_num, col_num, columns[col_num], font_style)  # at 0 row 0 column

    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()

    incident_reports = (
        IncidentReport.objects.annotate(total=Func("id", function="Count"))
        .filter(
            test_flag=False,
            reported_by=OuterRef("pk"),
        )
        .values("total")
    )
    if from_date:
        incident_reports = incident_reports.filter(created_at__gte=from_date)
    if to_date:
        incident_reports = incident_reports.filter(created_at__lte=to_date)

    zero_reports = (
        ZeroReport.objects.annotate(total=Func("id", function="Count"))
        .filter(reported_by=OuterRef("pk"))
        .values("total")
    )
    if from_date:
        zero_reports = zero_reports.filter(created_at__gte=from_date)
    if to_date:
        zero_reports = zero_reports.filter(created_at__lte=to_date)

    rows = (
        AuthorityUser.objects.filter(authority__in=sub_authorities)
        .annotate(
            incident_reports=Subquery(incident_reports),
            zero_reports=Subquery(zero_reports),
        )
        .order_by("username")
        .values(
            "username",
            "first_name",
            "last_name",
            "telephone",
            "authority__name",
            "incident_reports",
            "zero_reports",
        )
    )
    # print(rows.query)

    for row in rows:
        row_num += 1
        col_num = 0
        for item in row:
            ws.write(row_num, col_num, row[item], font_style)
            col_num += 1

    wb.save(response)

    return response
    # return HttpResponse("return this string")


def write_header(
    row_num,
    left_column,
    right_column,
    ws,
    title,
    from_date,
    to_date,
    authority,
):
    sty_header = xlwt.easyxf(
        "font: bold True;"
        "pattern: pattern solid, fore_color gray25;"
        "alignment: horizontal center;"
    )
    ws.write_merge(row_num, row_num, left_column, right_column, title, sty_header)
    row_num += 1
    ws.write_merge(
        row_num,
        row_num,
        left_column,
        right_column,
        f'From {from_date.strftime("%d-%b-%Y")} To {to_date.strftime("%d-%b-%Y")}',
        sty_header,
    )
    row_num += 1

    ws.write_merge(
        row_num,
        row_num,
        left_column,
        right_column,
        f"Authority {authority.name}",
        sty_header,
    )
    row_num += 1
    return row_num
