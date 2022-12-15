from django.contrib.gis.measure import Distance

from cases.models import Case
from podd_api.celery import app

from accounts.models import Place as CommonPlace
from notifications.models import Message as NotificationMessage
from outbreaks.models import Plan, Place, Message


@app.task
def evaluate_outbreak_plan(case_id, to_step_id):
    case = Case.objects.get(id=case_id)
    plans = Plan.objects.filter(
        report_type=case.report.report_type,
        state_step_id=to_step_id,
    )
    center = case.report.gps_location
    for plan in plans:
        previous_distance = None
        outbreak_plan_info = {"zones": []}
        for zone_number in range(1, 4):
            prefix = f"zone{zone_number}_"
            radius_attr = f"{prefix}radius"
            radius = getattr(plan, radius_attr)
            distance = None
            if radius:
                distance = Distance(m=radius)
                title_attr = f"{prefix}message_title"
                body_attr = f"{prefix}message_body"
                color_attr = f"{prefix}color"

                title = getattr(plan, title_attr, None)
                body = getattr(plan, body_attr, None)
                color = getattr(plan, color_attr, None)

                outbreak_plan_info["zones"].append(
                    {
                        "radius": radius,
                        "color": color,
                    }
                )

                notification_message = None
                if body:
                    notification_message = NotificationMessage.objects.create(
                        title=title,
                        body=body,
                    )
                # create Message
                outbreak_message = None
                if notification_message:
                    outbreak_message = Message.create_outbreak_message(
                        case, plan, zone_number, notification_message
                    )

                # find place that match the radius
                query = CommonPlace.objects.filter(
                    location__distance_lt=(center, distance)
                )
                if previous_distance:
                    query = query.filter(
                        location__distance_gte=(center, previous_distance)
                    )

                for place in query.all():
                    # for each place, create outbreak.models.Place
                    Place.create_outbreak_place(case, plan, place, zone_number, color)
                    if place.notification_to and outbreak_message:
                        outbreak_message.message.send(place.notification_to)

            previous_distance = distance

        # update oubreak_plan_info field in case table
        if len(outbreak_plan_info["zones"]) > 0:
            case.outbreak_plan_info = outbreak_plan_info
            case.save()
