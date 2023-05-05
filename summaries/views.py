from datetime import datetime, timedelta, timezone
from decimal import Decimal
from django.http import HttpResponse
from accounts.models import Authority, AuthorityUser
import xlwt
from django.utils.dateparse import parse_datetime
from reports.models.report import IncidentReport, ZeroReport
from django.db.models import Count, OuterRef, Subquery, Func

from reports.models.report_type import ReportType
import json
import urllib.parse

# Create your views here.


def export_inactive_reporter_xls(request):
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date = parse_date_from_str(request)

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

    from_date, to_date = parse_date_from_str(request)

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


def export_incident_report_xls(request):
    form = None
    authority_id = request.GET.get("authorityId")
    authority = Authority.objects.get(pk=authority_id)
    sub_authorities = authority.all_inherits_down()

    from_date, to_date = parse_date_from_str(request)

    report_type = ReportType.objects.get(pk=request.GET.get("reportTypeId"))
    if request.GET.get("columnSplit") is not None:
        form = parseForm(report_type.definition)

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = "attachment; filename=%s" % urllib.parse.quote(
        f"report_{report_type.name}.xls"
    )
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Reporter Performance")

    # Sheet header, first row
    row_num = 4

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    col_num = 0
    columns = [
        "CREATED AT",
        "INCIDENT DATE",
    ]
    if form is None:
        columns.append("DATA")
        col_num = 2

    for col_num in range(len(columns)):
        cwidth = ws.col(col_num).width
        if (len(columns[col_num]) * 367) > cwidth:
            ws.col(col_num).width = (
                len(columns[col_num]) * 367
            )  # (Modify column width to match biggest data in that column)

        ws.write(row_num, col_num, columns[col_num], font_style)  # at 0 row 0 column

    if form is not None:
        col_num = 2
        for section in form.sections:
            # print("section : " + section.label)
            for question in section.questions:
                print(f"question : {str(question.name)}")
                for field in question.fields:
                    print(f"field : {field.name}")
                    ws.write(
                        row_num, col_num, field.name, font_style
                    )  # at 0 row 0 column
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
        .values("created_at", "incident_date", "data")
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
                                ws.write(
                                    row_num, col_num, field.renderedValue, font_style
                                )
                                col_num += 1
            elif type(row[item]) == datetime:
                # print(f"{item} {row[item]}")
                ws.write(
                    row_num,
                    col_num,
                    str(row[item].strftime("%d-%b-%Y %H:%M:%S")),
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

    return from_date, to_date


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


def parseForm(json):
    form = Form(json.get("id", 0))
    form.sections = list(map(parseSection, json.get("sections")))
    form.registerValues()
    return form


def parseSection(json):
    section = Section(json.get("label"), "")
    section.questions = list(map(parseQuestion, json.get("questions")))
    return section


def parseQuestion(json):
    question = Question(
        json.get("label"),
        {
            "name": json.get("name", None),
            "description": json.get("description", None),
            "condition": parseCondition(json.get("condition")),
        },
    )
    question.fields = list(map(parseField, json.get("fields")))
    return question


def parseField(json):
    commonParams = {
        "label": json.get("label", ""),
        "description": json.get("description", ""),
        "required": json.get("required", False),
        "requiredMessage": json.get("requiredMessage", ""),
        "suffixLabel": json.get("suffixLabel", ""),
        "condition": parseCondition(json.get("condition")),
        "tags": json.get("tags", ""),
    }
    if json["type"] == "text":
        return TextField(
            json.get("id", 0),
            json.get("name", ""),
            {
                **commonParams,
                "minLength": json.get("minLength", 0),
                "minLengthMessage": json.get("minLengthMessage", ""),
                "maxLength": json.get("maxLength", 0),
                "maxLengthMessage": json.get("maxLengthMessage", ""),
            },
        )

    elif json["type"] == "integer":
        return IntegerField(
            json["id"],
            json["name"],
            {
                **commonParams,
                "min": json.get("min"),
                "minMessage": json.get("minMessage"),
                "max": json.get("max"),
                "maxMessage": json.get("maxMessage"),
            },
        )
    elif json["type"] == "decimal":
        return DecimalField(json.get("id"), json.get("name"), commonParams)
    elif json["type"] == "date":
        return DateField(
            json["id"],
            json["name"],
            {
                **commonParams,
                "withTime": json.get("withTime"),
                "backwardDaysOffset": json.get("backwardDaysOffset"),
                "forwardDaysOffset": json.get("forwardDaysOffset"),
            },
        )
    elif json["type"] == "location":
        return LocationField(json["id"], json["name"], commonParams)
    elif json["type"] == "singlechoices":
        return SingleChoicesField(
            json.get("id"), json.get("name"), json.get("options"), commonParams
        )
    elif json["type"] == "multiplechoices":
        return MultipleChoicesField(
            json.get("id", 0), json.get("name"), json.get("options"), commonParams
        )
    elif json["type"] == "images":
        return ImagesField(
            json.get("id"),
            json.get("name"),
            {
                **commonParams,
                "min": json.get("min"),
                "minMessage": json.get("minMessage"),
                "max": json.get("max"),
                "maxMessage": json.get("maxMessage"),
            },
        )
    else:
        return Field(
            json.get("id", 0),
            json.get("name", ""),
            commonParams,
        )


def parseCondition(json):
    if json is not None:
        return SimpleCondition(
            json.get("name"), json.get("operator"), json.get("value")
        )

    return None


class SimpleCondition:
    def __init__(self, name, operator, value):
        self.name = name
        self.operator = operator
        self.value = value


class Question:
    def __init__(self, label, params):
        self.label = label
        self.name = params["name"]
        self.description = params["description"]
        self.condition = params["condition"]

    def registerValues(self, parentValues, form):
        self.form = form
        currentValues = parentValues
        if self.name:
            self.values = Values(parentValues)
            parentValues.setValues(self.name, self.values)
            currentValues = self.values

        for field in self.fields:
            field.registerValues(currentValues, form)

    def loadJsonValue(self, json):
        evaluateJson = json
        if self.name is not None and json[self.name] is not None:
            evaluateJson = json[self.name]

        for field in self.fields:
            field.loadJsonValue(evaluateJson)


class Section:
    def __init__(self, label, description):
        self.label = label
        self.description = description

    def registerValues(self, values, form):
        self.form = form
        for question in self.questions:
            question.registerValues(values, form)

    def loadJsonValue(self, json):
        for question in self.questions:
            question.loadJsonValue(json)


class Form:
    def __init__(self, id):
        self.id = id
        self.values = Values(None)

    def registerValues(self):
        for section in self.sections:
            section.registerValues(self.values, self)
        return self.values

    def loadJsonValue(self, json):
        for section in self.sections:
            section.loadJsonValue(json)


class Field:
    def __init__(self, id, name, params):
        self.id = id
        self.name = name
        self.label = params["label"]
        self.description = params["description"]
        self.suffixLabel = params["suffixLabel"]
        self.required = params["required"]
        self.requiredMessage = params["requiredMessage"]
        self.condition = params["condition"]
        self.tags = params["tags"]

    def registerValues(self, values, form):
        self.form = form
        values.setValueDelegate(self.name, ValueDelegate(self))

    def loadJsonValue(self, json):
        self.value = json[self.name]

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        elif type(self.value) is list:
            return ", ".join(self.value)
        else:
            return str(self.value)


class PrimitiveField(Field):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)


class TextField(PrimitiveField):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)
        self.minLength = params["minLength"]
        self.maxLength = params["maxLength"]
        self.minLengthMessage = params["minLengthMessage"]
        self.maxLengthMessage = params["maxLengthMessage"]


class IntegerField(PrimitiveField):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)
        self.min = params["min"]
        self.max = params["max"]
        self.minMessage = params["minMessage"]
        self.maxMessage = params["maxMessage"]


class DecimalField(PrimitiveField):
    value = None

    def __init__(self, id, name, params):
        super().__init__(id, name, params)

    def loadJsonValue(self, json):
        try:
            self.value = Decimal(json[self.name])
        except:
            print("Something went wrong")

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        return "{:.2f}".format(self.value)


class DateField(Field):
    year = None
    month = None
    year = None
    hour = None
    hour = None

    def __init__(self, id, name, params):
        super().__init__(id, name, params)
        if params["withTime"]:
            self.withTime = True
        else:
            self.withTime = False
        self.backwardDaysOffset = params["backwardDaysOffset"]
        self.forwardDaysOffset = params["forwardDaysOffset"]

    def loadJsonValue(self, json):
        value = json[self.name]
        if value is not None:
            date = parse_datetime(value)
            self.day = date.day
            self.month = date.month
            self.year = date.year
            if self.withTime:
                self.hour = date.hour
                self.minute = date.minute

    @property
    def value(self):
        if (
            self.year is None
            or self.month is None
            or self.day is None
            or (self.withTime and (self.hour is None or self.minute is None))
        ):
            return None

        date = datetime(
            self.year,
            self.month,
            self.day,
        )

        if self.withTime:
            if self.hour is not None:
                date.replace(hour=self.hour)
            if self.minute is not None:
                date.replace(minute=self.minute)

        return date.isoformat()

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        else:
            if self.withTime:
                return parse_datetime(self.value).strftime("%Y-%m-%d %H:%M")
            else:
                return parse_datetime(self.value).strftime("%Y-%m-%d")


class SingleChoicesField(Field):
    def __init__(self, id, name, options, params):
        super().__init__(id, name, params)
        self.options = options

    def loadJsonValue(self, json):
        self.value = json[self.name]
        key = f"{self.name}_text"
        if key in json:
            self.text = json[key]

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        else:
            if self.text is not None:
                return str(self.value) + " - " + str(self.text)
            else:
                return str(self.value)


class MultipleChoicesField(Field):
    _selected = {}
    _text = {}
    _invalidTextMessage = {}

    def __init__(self, id, name, options, params):
        super().__init__(id, name, params)
        self.options = options
        for option in options:
            self._selected[option["value"]] = False
            if "textInput" in option:
                self._text[option["value"]] = None
                self._invalidTextMessage[option["value"]] = None

    def loadJsonValue(self, json):
        values = json[self.name]
        if values:
            for key, value in self._selected.items():
                if key in values:
                    self._selected[key] = values[key]
                textKey = f"{key}_text"
                if textKey in values:
                    self._text[key] = values[textKey]

    @property
    def renderedValue(self):
        values = []
        for option in self.options:
            if self._selected[option["value"]]:
                value = option["value"]
                if option["value"] in self._text:
                    value += " - " + self._text[option["value"]]
                values.append(value)

        return ", ".join(values)


class ImagesField(PrimitiveField):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)
        self.min = params["min"]
        self.max = params["max"]
        self.minMessage = params["minMessage"]
        self.maxMessage = params["maxMessage"]


class LocationField(PrimitiveField):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        else:
            return f"{self.value}  (Lng,Lat)"


class Values:
    def __init__(self, parent):
        self.parent = parent

    def setValueDelegate(self, name, delegate):
        pass
        # print("setValueDelegate")
        # self.values[name] = right(delegate)


class ValueDelegate:
    def __init__(self, getField):
        self.getField = getField
