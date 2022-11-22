from django.db import models

from common.models import BaseModel, BaseModelManager
from accounts.models import Place as CommonPlace
from cases.models import StateStep, Case
from notifications.models import Message as NotificationMessage
from reports.models import ReportType


class Plan(BaseModel):
    objects = BaseModelManager()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)
    state_step = models.ForeignKey(StateStep, on_delete=models.CASCADE)
    zone1_color = models.CharField(max_length=7, blank=True)
    zone1_radius = models.FloatField(null=True, blank=True)
    zone1_message_title = models.CharField(max_length=200, blank=True)
    zone1_message_body = models.TextField(blank=True)
    zone2_color = models.CharField(max_length=7, blank=True)
    zone2_radius = models.FloatField(null=True, blank=True)
    zone2_message_title = models.CharField(max_length=200, blank=True)
    zone2_message_body = models.TextField(blank=True)
    zone3_color = models.CharField(max_length=7, blank=True)
    zone3_radius = models.FloatField(null=True, blank=True)
    zone3_message_title = models.CharField(max_length=200, blank=True)
    zone3_message_body = models.TextField(blank=True)


class Message(BaseModel):
    plan = models.ForeignKey(Plan, related_name="messages", on_delete=models.CASCADE)
    message = models.ForeignKey(NotificationMessage, on_delete=models.CASCADE)
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="outbreak_messages"
    )

    @classmethod
    def create_outbreak_message(cls, case, plan, zone_number, message):
        return Message.objects.create(plan=plan, case=case, message=message)


class Place(BaseModel):
    plan = models.ForeignKey(Plan, related_name="places", on_delete=models.CASCADE)
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name="outbreak_places"
    )
    place = models.ForeignKey(
        CommonPlace, on_delete=models.CASCADE, related_name="outbreak_places"
    )
    zone = models.IntegerChoices("zone", "1 2 3")
    color = models.CharField(max_length=7)

    @classmethod
    def create_outbreak_place(cls, case, plan, place, zone_number, color):
        return Place.objects.create(
            plan=plan,
            case=case,
            place=place,
            zone=zone_number,
            color=color,
        )
