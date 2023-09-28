from datetime import datetime
from decimal import Decimal
from django.utils.dateparse import parse_datetime


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

    def toJsonValue(self, json):
        currentJson = json
        if self.name is not None:
            currentJson = {}
            json[self.name] = currentJson

        for field in self.fields:
            field.toJsonValue(currentJson)


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

    def toJsonValue(self, json):
        for question in self.questions:
            question.toJsonValue(json)


class Form:
    def __init__(self, id):
        self.id = id
        self.values = Values(None)
        self.report_td = ""
        self.header = {}

    def registerValues(self):
        for section in self.sections:
            section.registerValues(self.values, self)
        return self.values

    def loadJsonValue(self, json):
        for section in self.sections:
            section.loadJsonValue(json)

    def toJsonValue(self):
        json = {}
        # this.subforms.forEach(subform => subform.toJsonValue());
        for section in self.sections:
            section.toJsonValue(json)
        return json

    def toJsonValue(self):
        json = {}
        # this.subforms.forEach(subform => subform.toJsonValue());
        for section in self.sections:
            section.toJsonValue(json)
        return json

    def toJsonDataFrameValue(self, report_td, data, incident_data, header={}):
        self.report_td = report_td
        self.header = header
        self.loadJsonValue(data)
        value = self.toJsonValue()
        list = []
        data = {"__name": "df"}
        data[header.get("__reportId", "__reportId")] = self.report_td
        for item in incident_data:
            if item in header:
                data[header[item]] = incident_data[item]
            else:
                data[item] = incident_data[item]

        list.append(data)
        for key in value:
            if self.__isSubform(key):
                list = list + value[key]
            else:
                data[key] = value[key]
        return list

    def toJsonDataHeaders(self):
        json = {}
        for section in self.sections:
            for question in section.questions:
                for field in question.fields:
                    json[field.name] = field.label or field.name
        return json

    def __isSubform(self, fieldName):
        for section in self.sections:
            for question in section.questions:
                for field in question.fields:
                    if field.name == fieldName and field.type == "subform":
                        return field
        return None


class Field:
    def __init__(self, id, name, params):
        # print("__init__", name, params)
        self.id = id
        self.name = name
        self.type = params["type"]
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
        if self.name in json:
            self.value = json[self.name]
        else:
            self.value = ""

    def toJsonValue(self, json):
        # print(self.name + "-" + self.label + "-" + str(self.type))
        json[self.name] = self.value
        # json[self.name + "__value"] = self.renderedValue

    @property
    def renderedValue(self):
        if not hasattr(self, "value"):
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
        value = json.get(self.name, None)
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
        if self.name in json:
            self.value = json[self.name]
            key = f"{self.name}_text"
            if key in json:
                self.text = json[key]
        else:
            self.value = None
            self.text = None

    def toJsonValue(self, json):
        json[self.name] = self.value or ""
        json[self.name + "_text"] = self.text or ""
        # json[self.name + "__value"] = self.renderedValue

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
    def __init__(self, id, name, options, params):
        super().__init__(id, name, params)
        self._selected = {}
        self._text = {}
        self._invalidTextMessage = {}
        self.options = options
        for option in options:
            self._selected[option["value"]] = False
            if "textInput" in option:
                self._text[option["value"]] = None
                self._invalidTextMessage[option["value"]] = None

    def loadJsonValue(self, json):
        try:
            if self.name in json:
                values = json[self.name]
                if values:
                    for key, value in self._selected.items():
                        if key in values:
                            self._selected[key] = values[key]
                        textKey = f"{key}_text"
                        if textKey in values:
                            self._text[key] = values[textKey]
        except:
            pass

    def toJsonValue(self, json):
        values = {}
        for key, value in self._selected.items():
            values[key] = value

        for key, value in self._text.items():
            values[key + "_text"] = value

        values["value"] = self.value
        json[self.name] = values
        # json[self.name + "__value"] = self.renderedValue

    @property
    def value(self):
        values = []
        for option in self.options:
            if self._selected[option["value"]]:
                values.append(option["value"])

        return ", ".join(values)

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

    def format(self, value):
        index = value.index(".")
        return value[0 : index + 6]

    @property
    def renderedValue(self):
        if self.value is None:
            return ""
        else:
            return f"{self.value}  (Lng,Lat)"

    @property
    def longitude(self):
        if self.value is None:
            return ""
        else:
            return self.format(self.value.split(",")[0])

    @property
    def latitude(self):
        if self.value is None:
            return ""
        else:
            return self.format(self.value.split(",")[1])

    def toJsonValue(self, json):
        json["location"] = self.value
        # json["location__value"] = self.renderedValue


class SubformField(PrimitiveField):
    def __init__(self, id, name, params):
        super().__init__(id, name, params)
        self.formRef = params["formRef"]
        self.titleTemplate = params["titleTemplate"]
        self.descriptionTemplate = params["descriptionTemplate"]

    def loadJsonValue(self, json):
        if self.name in json:
            self.value = json[self.name]
        else:
            self.value = None

    def toJsonValue(self, json):
        if self.value is None:
            return []
        if type(self.value) != type(dict()):
            return []

        try:
            values = []
            json[self.name] = values
            subform = next(
                (x for x in self.form.subforms if x.id == self.formRef), None
            )
            for key, value in self.value.items():
                if type(value) == type(dict()):
                    subform.loadJsonValue(value)
                    data = {}
                    data["__name"] = self.name
                    data[
                        self.form.header.get("__reportId", "__reportId")
                    ] = self.form.report_td
                    data["__key"] = key
                    data = {**data, **subform.toJsonValue()}
                    values.append(data)
            return values
        except:
            return []

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


def parseForm(json):
    form = Form(json.get("id", 0))
    if json.get("subforms") is not None:
        form.subforms = parseSubform(json.get("subforms"))
    form.sections = list(map(parseSection, json.get("sections")))
    form.registerValues()
    return form


def parseSubform(json):
    subforms = []
    for id, formType in json.items():
        subform = Form(id)
        subform.sections = list(map(parseSection, formType.get("sections")))
        subform.registerValues()
        subforms.append(subform)
    return subforms


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
        "type": json.get("type", ""),
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
        return LocationField(json["id"], json["name"] or "location", commonParams)
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
    elif json["type"] == "subform":
        return SubformField(
            json.get("id"),
            json.get("name"),
            {
                **commonParams,
                "formRef": json.get("formRef"),
                "titleTemplate": json.get("titleTemplate"),
                "descriptionTemplate": json.get("descriptionTemplate"),
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
