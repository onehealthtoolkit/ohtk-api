from datetime import datetime, timedelta, timezone
from django.http import HttpResponse
from accounts.models import Authority, AuthorityUser
import xlwt
from django.utils.dateparse import parse_datetime
from reports.models.report import IncidentReport, ZeroReport
from django.db.models import Count, OuterRef, Subquery, Func

from reports.models.report_type import ReportType
from .models import (
    LocationField,
    parseForm,
)
import json
import urllib.parse

# Create your views here.


def export_inactive_reporter_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date, tzinfo = parse_date_from_str(request)

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

    for row in rows:
        row_num += 1
        col_num = 0
        for item in row:
            auto_column_width(ws, col_num, row[item])
            ws.write(row_num, col_num, row[item], font_style)
            col_num += 1

    wb.save(response)

    return response
    # return HttpResponse("return this string")


def export_reporter_performance_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date, tzinfo = parse_date_from_str(request)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="reporter_performance.xls"'

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Reporter Performance")

    # Sheet header, first row
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    row_num = write_header(
        row_num, 0, 6, ws, "Reporter Performance", from_date, to_date, authority
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
        auto_column_width(ws, col_num, columns[col_num])
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
            zero_reports=Subquery(zero_reports),
            incident_reports=Subquery(incident_reports),
        )
        .order_by("username")
        .values(
            "username",
            "first_name",
            "last_name",
            "telephone",
            "authority__name",
            "zero_reports",
            "incident_reports",
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


def export_incident_report_xls(request):
    form = None
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date, tzinfo = parse_date_from_str(request)

    report_type = ReportType.objects.get(pk=request.GET.get("reportTypeId"))
    if request.GET.get("columnSplit") is not None:
        form = parseForm(report_type.definition)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = "attachment; filename=%s" % urllib.parse.quote(
        f"report_{report_type.name}.xls"
    )
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Reports")

    # Sheet header, first row
    row_num = 4

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    col_num = 0
    columns = [
        "CREATED AT",
        "INCIDENT DATE",
        "REPORT BY ID",
        "REPORT BY NAME",
        "CASE_ID",
        "ID",
    ]
    if form is None:
        columns.append("DATA")
        col_num = 6

    for col_num in range(len(columns)):
        auto_column_width(ws, col_num, columns[col_num])
        ws.write(row_num, col_num, columns[col_num], font_style)  # at 0 row 0 column

    if form is not None:
        col_num = 6
        for section in form.sections:
            # print("section : " + section.label)
            for question in section.questions:
                # print(f"question : {str(question.name)}")
                for field in question.fields:
                    # print(f"field : {field.name} type {str(type(field))}")
                    if type(field) == LocationField:
                        ws.write(row_num, col_num, "LONGITUDE", font_style)
                        col_num += 1
                        ws.write(row_num, col_num, "LATITUDE", font_style)
                        col_num += 1
                    else:
                        ws.write(row_num, col_num, field.name, font_style)
                        col_num += 1

    row_num = 0
    row_num = write_header(
        row_num,
        0,
        col_num,
        ws,
        "Incident Reports",
        from_date,
        to_date,
        authority,
        report_type,
    )

    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()
    font_style.alignment.vert = xlwt.Alignment.VERT_TOP
    rows = (
        IncidentReport.objects.all()
        .order_by("-created_at")
        .prefetch_related("images", "reported_by", "report_type")
        .filter(
            relevant_authorities__in=sub_authorities,
            test_flag=False,
            report_type=report_type,
        )
        .values(
            "created_at",
            "incident_date",
            "reported_by__id",
            "reported_by__first_name",
            "case_id",
            "id",
            "data",
        )
    )
    if from_date:
        rows = rows.filter(created_at__gte=from_date)
    if to_date:
        rows = rows.filter(created_at__lte=to_date)

    # print(rows.query)

    row_num = 4
    for row in rows:
        row_num += 1
        col_num = 0

        # print(json.dumps(data, indent=2))
        # renderJson(data)
        for item in row:
            # print(type(row[item]))
            if type(row[item]) == type(dict()):
                # print(json.dumps(row[item], indent=2))
                if form is None:
                    ws.write(
                        row_num, col_num, json.dumps(row[item], indent=2), font_style
                    )
                else:
                    # print(row["data"])
                    data = row["data"]
                    form.loadJsonValue(data)
                    for section in form.sections:
                        for question in section.questions:
                            for field in question.fields:
                                # print(f"field : {field.name} value : {field.renderedValue}")
                                if type(field) == LocationField:
                                    ws.write(
                                        row_num,
                                        col_num,
                                        field.longitude,
                                        font_style,
                                    )
                                    col_num += 1
                                    ws.write(
                                        row_num,
                                        col_num,
                                        field.latitude,
                                        font_style,
                                    )
                                    col_num += 1
                                else:
                                    ws.write(
                                        row_num,
                                        col_num,
                                        field.renderedValue,
                                        font_style,
                                    )
                                    col_num += 1
            elif type(row[item]) == datetime:
                # print(f"{item} {row[item]}")
                value = row[item].replace(tzinfo=tzinfo)
                ws.write(
                    row_num,
                    col_num,
                    str(value.astimezone().strftime("%d-%b-%Y %H:%M:%S")),
                    font_style,
                )
            else:
                ws.write(row_num, col_num, str(row[item]), font_style)
            col_num += 1

    wb.save(response)

    return response
    # return HttpResponse("return this string")


def parse_date_from_str(request):
    tzinfo = timezone(timedelta(minutes=int(request.GET.get("timezoneOffset"))))
    from_date = parse_datetime(request.GET.get("fromDate"))
    if from_date is not None:
        from_date = from_date.replace(tzinfo=tzinfo)

    to_date = parse_datetime(request.GET.get("toDate"))
    if to_date is not None:
        to_date = to_date.replace(tzinfo=tzinfo)

    return from_date, to_date, tzinfo


def auto_column_width(ws, col_num, value):
    cwidth = ws.col(col_num).width
    if (value is not None and len(value) * 367) > cwidth:
        ws.col(col_num).width = (
            len(value) * 367
        )  # (Modify column width to match biggest data in that column)


def write_header(
    row_num,
    left_column,
    right_column,
    ws,
    title,
    from_date,
    to_date,
    authority,
    report_type=None,
):
    # fx = from_date + timedelta(minutes=-420)
    # fx = datetime(
    #     from_date.year,
    #     from_date.month,
    #     from_date.day,
    #     17,
    #     0,
    #     0,
    #     0,
    #     tzinfo=timezone(timedelta(minutes=-420)),
    # )
    # fx = from_date
    # fx = from_date.replace(tzinfo=timezone(timedelta(minutes=-420)))
    # print(f"fx --- >{fx.strftime('%Y-%m-%d %H:%M:%S.%f')}")

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
        f'From {from_date.astimezone().strftime("%d-%b-%Y")} To {to_date.astimezone().strftime("%d-%b-%Y")}',
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

    if report_type is not None:
        ws.write_merge(
            row_num,
            row_num,
            left_column,
            right_column,
            f"Report  {report_type.name}",
            sty_header,
        )
        row_num += 1

    return row_num


def renderJson(data, definition):
    for key, value in data.items():
        if type(value) == type(dict()):
            renderJson(value)
        else:
            print(str(key) + "->" + str(value))
