from datetime import datetime, timedelta, timezone
from django.http import HttpResponse
from accounts.models import Authority, AuthorityUser
import xlwt
from django.utils.dateparse import parse_datetime
from observations.models import Definition, MonitoringRecord, SubjectRecord
from reports.models.report import IncidentReport, ZeroReport
from django.db.models import Count, OuterRef, Subquery, Func

from reports.models.report_type import ReportType
from .models import (
    parseForm,
)
import json
import urllib.parse
import pandas as pd
import tempfile
from django.http import FileResponse
import os
from django.db.models.functions import TruncDay

# Create your views here.


def export_inactive_reporter_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()
    dataFrameFormat = request.GET.get("dataFrameFormat")

    from_date, to_date, tzinfo = parse_date_from_str(request)

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
        .filter(authority__in=sub_authorities, role=AuthorityUser.Role.REPORTER)
        .values("username", "first_name", "last_name", "telephone", "authority__name")
    )

    if dataFrameFormat is not None:
        return responseQuerySetExcel(rows, "inactive_reporter")
    else:
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
            ws.write(
                row_num, col_num, columns[col_num], font_style
            )  # at 0 row 0 column

        # Sheet body, remaining rows
        font_style = xlwt.XFStyle()

        response = HttpResponse(content_type="application/ms-excel")
        response["Content-Disposition"] = 'attachment; filename="inactive_reporter.xls"'

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
    dataFrameFormat = request.GET.get("dataFrameFormat")

    from_date, to_date, tzinfo = parse_date_from_str(request)

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
        AuthorityUser.objects.filter(
            authority__in=sub_authorities, role=AuthorityUser.Role.REPORTER
        )
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
    if dataFrameFormat is not None:
        return responseQuerySetExcel(rows, "reporter_performance")
    else:
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
            ws.write(
                row_num, col_num, columns[col_num], font_style
            )  # at 0 row 0 column

        # Sheet body, remaining rows
        font_style = xlwt.XFStyle()
        response = HttpResponse(content_type="application/ms-excel")
        response[
            "Content-Disposition"
        ] = 'attachment; filename="reporter_performance.xls"'

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
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()
    columnSplit = request.GET.get("columnSplit")

    from_date, to_date, tzinfo = parse_date_from_str(request)

    report_type = ReportType.objects.get(pk=request.GET.get("reportTypeId"))
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

    if columnSplit is not None:
        form = parseForm(report_type.definition)
        dataList = []
        headers = {
            "__created_at": "CREATED AT",
            "__incident_date": "INCIDENT DATE",
            "__reported_by__id": "REPORT BY ID",
            "__reported_by__first_name": "REPORT BY NAME",
            "__case_id": "CASE ID",
            "__reportId": "Report ID",
        }
        for row in rows:
            incidentReport = IncidentReport.objects.get(pk=row["id"])
            form = parseForm(incidentReport.definition or report_type.definition)
            # form.loadJsonValue(incidentReport.data)
            dataList = dataList + form.toJsonDataFrameValue(
                report_td=str(row["id"]),
                data=row["data"],
                incident_data={
                    "__created_at": str(
                        row["created_at"].astimezone().strftime("%d-%b-%Y %H:%M:%S")
                    ),
                    "__incident_date": row["incident_date"].strftime(
                        "%d-%b-%Y %H:%M:%S"
                    ),
                    "__reported_by__id": row["reported_by__id"],
                    "__reported_by__first_name": row["reported_by__first_name"],
                    "__case_id": str(row["case_id"]),
                },
                header=headers,
            )
        return responseJsonExcel(
            dataList,
            f"report_{report_type.name}",
            header={
                "title": "Incident Reports",
                "from_date": from_date,
                "to_date": to_date,
                "authority": authority,
                "report_type": report_type,
            },
        )

    else:
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
            "DATA",
        ]

        for col_num in range(len(columns)):
            auto_column_width(ws, col_num, columns[col_num])
            ws.write(
                row_num, col_num, columns[col_num], font_style
            )  # at 0 row 0 column

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
        # print(rows.query)

        response = HttpResponse(content_type="application/ms-excel")
        response[
            "Content-Disposition"
        ] = "attachment; filename=%s" % urllib.parse.quote(
            f"report_{report_type.name}.xls"
        )
        row_num = 4
        for row in rows:
            row_num += 1
            col_num = 0
            for item in row:
                # print(type(row[item]))
                if type(row[item]) == type(dict()):
                    # print(json.dumps(row[item], indent=2))
                    ws.write(
                        row_num, col_num, json.dumps(row[item], indent=2), font_style
                    )
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


def export_zero_report_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date, tzinfo = parse_date_from_str(request)

    rows = (
        ZeroReport.objects.annotate(day=TruncDay("created_at"))
        .order_by("-day")
        .filter(
            reported_by__in=AuthorityUser.objects.filter(
                authority__in=sub_authorities
                # , role=AuthorityUser.Role.REPORTER
            ),
        )
        .values(
            "day",
            "reported_by__username",
            "reported_by__first_name",
            "reported_by__last_name",
            "reported_by__authorityuser__authority__name",
        )
        .annotate(total=Count("id"))
    )
    if from_date:
        rows = rows.filter(created_at__gte=from_date)
    if to_date:
        rows = rows.filter(created_at__lte=to_date)

    # print(rows.query)
    dataList = []
    for row in rows:
        username = row["reported_by__username"]
        data = next((x for x in dataList if x["username"] == username), None)
        if data is None:
            data = {
                "Name": row["reported_by__first_name"]
                + " "
                + row["reported_by__last_name"],
                "username": username,
                "Authority": row["reported_by__authorityuser__authority__name"],
            }
            for i in range(to_date.astimezone().day):
                data["Day " + str(i + 1)] = ""
            dataList.append(data)
        data["Day " + str(row["day"].day)] = row["total"]
    # print(json.dumps(dataList, indent=4))
    # for item in dataList:
    #     item.pop("user_id")

    if len(dataList) == 0:
        dataList.append({"Data not found.": ""})

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        with open(tmp.name, "w") as fi:
            with pd.ExcelWriter(tmp.name) as writer:
                df = pd.DataFrame(dataList)
                # print(df)
                df.to_excel(
                    writer,
                    sheet_name="zero_report",
                    index=False,
                    startrow=4,
                )
                # workbook = writer.book
                worksheet = writer.sheets["zero_report"]
                worksheet.merge_cells("A1:D1")
                worksheet["A1"] = "Zero Report"
                worksheet.merge_cells("A2:D2")
                worksheet[
                    "A2"
                ] = f'From {from_date.astimezone().strftime("%d-%b-%Y")} To {to_date.astimezone().strftime("%d-%b-%Y")}'
                worksheet.merge_cells("A3:D3")
                worksheet["A3"] = f"Authority {authority.name}"
                worksheet.column_dimensions["A"].width = 30

        response = FileResponse(open(tmp.name, "rb"))
        response[
            "Content-Disposition"
        ] = "attachment; filename=%s" % urllib.parse.quote(
            f'zero_report_{from_date.astimezone().strftime("%m_%Y")}.xlsx'
        )
        return response
    finally:
        os.remove(tmp.name)
    # return HttpResponse(json.dumps(dataList, indent=4))


def export_observation_xls(request):
    definition_id = request.GET.get("definitionId")
    definition = Definition.objects.get(pk=definition_id)

    from_date, to_date, tzinfo = parse_date_from_str(request)

    rows = (
        SubjectRecord.objects.all()
        .order_by("-created_at")
        .filter(
            definition=definition,
        )
        .values(
            "id",
            "created_at",
            "identity",
            "title",
            "description",
            "definition__register_form_definition",
            "form_data",
        )
    )
    if from_date:
        rows = rows.filter(created_at__gte=from_date)
    if to_date:
        rows = rows.filter(created_at__lte=to_date)
    if from_date is None and to_date is None:
        rows = rows.order_by("-id")[:100]

    # print(rows.query)
    dataList = []
    headers = {
        "__created_at": "CREATED AT",
        "__reportId": "Record ID",
    }
    for row in rows:
        form = parseForm(row["definition__register_form_definition"])
        dataList = dataList + form.toJsonDataFrameValue(
            report_td=str(row["id"]),
            data=row["form_data"],
            incident_data={
                "__created_at": str(
                    row["created_at"].astimezone().strftime("%d-%b-%Y %H:%M:%S")
                ),
                "identity": row["identity"],
                "title": row["title"],
                "description": row["description"],
            },
            header=headers,
        )

    if len(dataList) == 0:
        dataList.append({"__name": "", "Data not found.": ""})

    monitoring_rows = (
        MonitoringRecord.objects.all()
        .order_by("-created_at")
        .filter(
            monitoring_definition__definition=definition,
        )
        .values(
            "subject__id",
            "created_at",
            "title",
            "description",
            "monitoring_definition__form_definition",
            "form_data",
        )
    )
    if from_date:
        monitoring_rows = monitoring_rows.filter(created_at__gte=from_date)
    if to_date:
        monitoring_rows = monitoring_rows.filter(created_at__lte=to_date)
    if from_date is None and to_date is None:
        monitoring_rows = monitoring_rows.order_by("-id")[:100]

    # print(rows.query)
    monitoringList = []
    headers = {
        "__created_at": "CREATED AT",
        "__reportId": "Record ID",
    }
    for row in monitoring_rows:
        form = parseForm(row["monitoring_definition__form_definition"])
        monitoringList = monitoringList + form.toJsonDataFrameValue(
            report_td=str(row["subject__id"]),
            data=row["form_data"],
            incident_data={
                "__created_at": str(
                    row["created_at"].astimezone().strftime("%d-%b-%Y %H:%M:%S")
                ),
                "title": row["title"],
                "description": row["description"],
            },
            header=headers,
        )

    if len(monitoringList) == 0:
        monitoringList.append({"__name": "", "Data not found.": ""})

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        with open(tmp.name, "w") as fi:
            with pd.ExcelWriter(tmp.name) as writer:
                for item in dataList:
                    item.pop("__name")
                df = pd.DataFrame(dataList)
                # print(df)
                df.to_excel(
                    writer,
                    sheet_name="observation",
                    index=False,
                    startrow=4,
                )
                # workbook = writer.book
                worksheet = writer.sheets["observation"]
                worksheet.merge_cells("A1:D1")
                worksheet["A1"] = "Observation Report"
                worksheet.merge_cells("A2:D2")
                worksheet["A2"] = f"Defination {definition.name}"

                worksheet.merge_cells("A3:D3")
                dtxt = ""
                if from_date:
                    dtxt += f'From {from_date.astimezone().strftime("%d-%b-%Y")}'
                if to_date:
                    dtxt += f'To {to_date.astimezone().strftime("%d-%b-%Y")}'
                worksheet["A3"] = dtxt

                worksheet.column_dimensions["A"].width = 30

                for item in monitoringList:
                    item.pop("__name")
                df = pd.DataFrame(monitoringList)
                df.to_excel(
                    writer,
                    sheet_name="monitoring",
                    index=False,
                    startrow=2,
                )
                worksheet = writer.sheets["monitoring"]
                worksheet.merge_cells("A1:D1")
                worksheet["A1"] = "Monitoring"
                worksheet.merge_cells("A2:D2")

                worksheet.column_dimensions["A"].width = 30

        response = FileResponse(open(tmp.name, "rb"))
        response[
            "Content-Disposition"
        ] = "attachment; filename=%s" % urllib.parse.quote(
            f'observation_report{"_"+from_date.astimezone().strftime("%m_%Y") if from_date else  ""}.xlsx'
        )
        return response
    finally:
        os.remove(tmp.name)
    # return HttpResponse(json.dumps(dataList, indent=4))


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


def responseQuerySetExcel(querySet, outputName):
    # print(list(querySet))
    df = pd.DataFrame(
        list(querySet),
    )
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        with open(tmp.name, "w") as fi:
            with pd.ExcelWriter(tmp.name) as writer:
                df.to_excel(writer, sheet_name="df", index=False)
        response = FileResponse(open(tmp.name, "rb"))
        response[
            "Content-Disposition"
        ] = "attachment; filename=%s" % urllib.parse.quote(f"{outputName}.xls")
        return response
    finally:
        os.remove(tmp.name)


def responseJsonExcel(dataList, outputName, header={}):
    # print(json.dumps(dataList, indent=4))
    data = {}
    for d in dataList:
        data.setdefault(d["__name"], []).append(d)

    if len(data) == 0:
        data = {"__name": [{"__name": "", "Data not found.": ""}]}

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        with open(tmp.name, "w") as fi:
            with pd.ExcelWriter(tmp.name) as writer:
                for key in data:
                    dv = data[key]
                    for item in dv:
                        item.pop("__name")
                    # print(json.dumps(dv, indent=4))

                    df = pd.DataFrame(dv)
                    # print(df)
                    df.to_excel(writer, sheet_name=key, index=False, startrow=5)
                    # workbook = writer.book
                    worksheet = writer.sheets[key]
                    worksheet.cell(
                        row=1,
                        column=1,
                        value=header["title"],
                    )
                    worksheet.cell(
                        row=2,
                        column=1,
                        value=f'From {header["from_date"].astimezone().strftime("%d-%b-%Y")} To {header["to_date"].astimezone().strftime("%d-%b-%Y")}',
                    )
                    worksheet.cell(
                        row=3,
                        column=1,
                        value=f'Authority {header["authority"].name}',
                    )
                    worksheet.cell(
                        row=4,
                        column=1,
                        value=f'Report  {header["report_type"].name}',
                    )
        response = FileResponse(open(tmp.name, "rb"))
        # response = HttpResponse(content_type="application/ms-excel")
        response[
            "Content-Disposition"
        ] = "attachment; filename=%s" % urllib.parse.quote(f"{outputName}.xlsx")
        return response
    finally:
        os.remove(tmp.name)
