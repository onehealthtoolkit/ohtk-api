"""Preserve legacy local-ID routing and accepted-image replay."""
from django.db.models import Q
from graphql import GraphQLError

from observations.models import MonitoringRecord, RecordImage, SubjectRecord


def resolve_legacy_image_parent(report_id, image_id):
    # A real parent ID is authoritative. Do not let a form-field search redirect
    # an explicit request to a different record that happens to reference imageId.
    record = SubjectRecord.objects.filter(pk=report_id).first()
    if record is None:
        record = MonitoringRecord.objects.filter(pk=report_id).first()
    if record is not None:
        return record
    # Legacy mobile retains a local reportId after the server assigns its parent
    # UUID. The old endpoint replays an accepted image by imageId even after its
    # form reference disappears. Keep that contract, deriving the parent from
    # the stored relationship rather than requiring the edited form to prove it.
    if image_id is not None:
        accepted = RecordImage.objects.filter(pk=image_id).first()
        if accepted is not None:
            record = accepted.record
            if isinstance(record, (SubjectRecord, MonitoringRecord)):
                active = type(record).objects.filter(pk=record.pk).first()
                if active is not None:
                    return active
    # Old queued callers can carry a local ID. Retain their form-field binding,
    # including a subject's original form when the current form has been edited.
    if image_id is not None:
        key = str(image_id)
        # Keep the old first-match order for an initial upload: current subject
        # forms, then current monitoring forms. An original subject form is only
        # an additional fallback, so it cannot redirect a formerly valid upload.
        record = SubjectRecord.objects.filter(
            Q(form_data__house_front__has_key=key)
            | Q(form_data__consent_image__has_key=key)
        ).first()
        if record is None:
            record = MonitoringRecord.objects.filter(
                Q(form_data__deploy_image__has_key=key)
                | Q(form_data__indoor_container_neg__has_key=key)
                | Q(form_data__outdoor_container_neg__has_key=key)
                | Q(form_data__outdoor_container_pos__has_key=key)
                | Q(form_data__indoor_container_neg__value__has_key=key)
            ).first()
        if record is None:
            record = SubjectRecord.objects.filter(
                Q(origin_form_data__house_front__has_key=key)
                | Q(origin_form_data__consent_image__has_key=key)
            ).first()
        if record is not None:
            return record
    raise GraphQLError("Record not found.", extensions={"code": "NOT_FOUND"})
