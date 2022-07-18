from datetime import timedelta

import graphene
from django.db.models import Count
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import Authority, AuthorityUser
from cases.models import Case
from cases.schema import CaseType
from reports.models import IncidentReport
from reports.schema.types import IncidentReportType


class StatType(graphene.ObjectType):
    open_case_count = graphene.Field(graphene.Int)
    reporter_count = graphene.Field(graphene.Int)
    official_count = graphene.Field(graphene.Int)


class EventType(graphene.ObjectType):
    cases = graphene.List(CaseType)
    reports = graphene.List(IncidentReportType)


class Query(graphene.ObjectType):
    stat_query = graphene.Field(StatType, authority_id=graphene.Int(required=True))
    events_query = graphene.Field(EventType, authority_id=graphene.Int(required=True))

    @staticmethod
    @login_required
    def resolve_stat_query(root, info, authority_id):
        user = info.context.user
        if (
            user.is_authority_user()
            and user.authorityuser.has_summary_view_permission_on(authority_id)
        ):
            authority = Authority.objects.get(pk=authority_id)
            sub_authorities = authority.all_inherits_down()
            counts = (
                AuthorityUser.objects.filter(authority__in=sub_authorities)
                .values("role")
                .annotate(total=Count("role"))
            )
            try:
                reporter_count = counts.get(role=AuthorityUser.Role.REPORTER)["total"]
            except AuthorityUser.DoesNotExist:
                reporter_count = 0

            try:
                officer_count = counts.get(role=AuthorityUser.Role.OFFICER)["total"]
            except AuthorityUser.DoesNotExist:
                officer_count = 0

            open_case_count = Case.objects.filter(
                authorities__in=sub_authorities, is_finished=False
            ).count()

            return {
                "open_case_count": open_case_count,
                "reporter_count": reporter_count,
                "official_count": officer_count,
            }
        else:
            raise GraphQLError("Permission denied.")

    @staticmethod
    @login_required
    def resolve_events_query(root, info, authority_id):
        user = info.context.user
        authority = Authority.objects.get(pk=authority_id)
        if (
            user.is_authority_user()
            and user.authorityuser.has_summary_view_permission_on(authority_id)
        ):
            from_date = now().today() - timedelta(days=30)

            sub_authorities = authority.all_inherits_down()
            cases = Case.objects.filter(
                authorities__in=sub_authorities, report__incident_date__gte=from_date
            )
            reports = IncidentReport.objects.filter(
                relevant_authorities__in=sub_authorities, incident_date__gte=from_date
            )

            return {"cases": cases, "reports": reports}
        else:
            raise GraphQLError("Permission denied.")
