from django.db.models import Prefetch


def case_status_prefetch():
    # Import locally: case models also depend on reports.
    from cases.models import Case

    return Prefetch(
        "cases",
        queryset=Case.objects.only(
            "id", "report_id", "is_finished", "close_source", "close_outcome"
        ),
        to_attr="report_case_statuses",
    )


def get_report_case_status(report):
    if not report.case_id:
        return None
    if hasattr(report, "report_case_statuses"):
        return next(
            (case for case in report.report_case_statuses if case.pk == report.case_id),
            None,
        )

    from cases.models import Case

    # Both IDs must agree. Never expose an unrelated case through a stale UUID.
    return (
        Case.objects.filter(pk=report.case_id, report_id=report.pk)
        .only("id", "report_id", "is_finished", "close_source", "close_outcome")
        .first()
    )
