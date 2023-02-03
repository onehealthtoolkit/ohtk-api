from datetime import timedelta

import graphene
from django.db.models.functions import TruncDay
from django.db.models import Count
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import Authority, AuthorityUser, User
from cases.models import Case
from cases.schema import CaseType
from reports.models import IncidentReport, ReportAggregateView
from reports.schema.types import IncidentReportType
from django.db.models import F


class StatType(graphene.ObjectType):
    open_case_count = graphene.Field(graphene.Int)
    reporter_count = graphene.Field(graphene.Int)
    official_count = graphene.Field(graphene.Int)


class EventType(graphene.ObjectType):
    cases = graphene.List(CaseType)
    reports = graphene.List(IncidentReportType)


class SummaryByCategoryType(graphene.ObjectType):
    category = graphene.String(required=True)
    ordering = graphene.Int(required=False)
    day = graphene.Date(required=True)
    total = graphene.Int(required=True)


class SummaryContributionType(graphene.ObjectType):
    day = graphene.Date(required=True)
    total = graphene.Int(required=True)


class Query(graphene.ObjectType):
    stat_query = graphene.Field(StatType, authority_id=graphene.Int(required=True))
    events_query = graphene.Field(EventType, authority_id=graphene.Int(required=True))
    summary_report_by_category_query = graphene.List(
        graphene.NonNull(SummaryByCategoryType),
        authority_id=graphene.Int(required=True),
        from_date=graphene.DateTime(required=False),
        to_date=graphene.DateTime(required=False),
    )
    summary_case_by_category_query = graphene.List(
        graphene.NonNull(SummaryByCategoryType),
        authority_id=graphene.Int(required=True),
        from_date=graphene.DateTime(required=False),
        to_date=graphene.DateTime(required=False),
    )

    summary_contribution_query = graphene.List(
        graphene.NonNull(SummaryContributionType),
        user_id=graphene.Int(required=True),
        from_date=graphene.DateTime(required=False),
        to_date=graphene.DateTime(required=False),
    )

    @staticmethod
    @login_required
    def resolve_stat_query(root, info, authority_id):
        user = info.context.user
        if (
            user.is_authority_user
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
            user.is_authority_user
            and user.authorityuser.has_summary_view_permission_on(authority_id)
        ):
            from_date = now().today() - timedelta(days=30)

            sub_authorities = authority.all_inherits_down()
            cases = Case.objects.filter(
                authorities__in=sub_authorities,
                report__incident_date__gte=from_date,
                report__test_flag=False,
            )
            reports = IncidentReport.objects.filter(
                relevant_authorities__in=sub_authorities,
                incident_date__gte=from_date,
                test_flag=False,
            )

            return {"cases": cases, "reports": reports}
        else:
            raise GraphQLError("Permission denied.")

    @staticmethod
    @login_required
    def resolve_summary_report_by_category_query(
        root, info, authority_id, from_date, to_date
    ):
        user = info.context.user
        authority = Authority.objects.get(pk=authority_id)
        if (
            user.is_authority_user
            and user.authorityuser.has_summary_view_permission_on(authority_id)
        ):
            sub_authorities = authority.all_inherits_down()
            q = (
                IncidentReport.objects.annotate(day=TruncDay("created_at"))
                .filter(relevant_authorities__in=sub_authorities, test_flag=False)
                .values(
                    "report_type__category__name",
                    "report_type__category__ordering",
                    "day",
                )
                .annotate(
                    category=F("report_type__category__name"),
                    ordering=F("report_type__category__ordering"),
                    total=Count("id"),
                )
                .order_by("report_type__category__ordering", "day")
            )
            # print(q.query)
            if from_date:
                q = q.filter(created_at__gte=from_date)

            if to_date:
                q = q.filter(created_at__lte=to_date)

            return q
        else:
            raise GraphQLError("Permission denied.")

    @staticmethod
    @login_required
    def resolve_summary_case_by_category_query(
        root, info, authority_id, from_date, to_date
    ):
        user = info.context.user
        authority = Authority.objects.get(pk=authority_id)
        if (
            user.is_authority_user
            and user.authorityuser.has_summary_view_permission_on(authority_id)
        ):
            sub_authorities = authority.all_inherits_down()
            q = (
                Case.objects.annotate(day=TruncDay("report__created_at"))
                .filter(authorities__in=sub_authorities, report__test_flag=False)
                .values(
                    "report__report_type__category__name",
                    "report__report_type__category__ordering",
                    "day",
                )
                .annotate(
                    category=F("report__report_type__category__name"),
                    ordering=F("report__report_type__category__ordering"),
                    total=Count("id"),
                )
                .order_by("report__report_type__category__ordering", "day")
            )
            # print(q.query)
            if from_date:
                q = q.filter(created_at__gte=from_date)

            if to_date:
                q = q.filter(created_at__lte=to_date)

            return q
        else:
            raise GraphQLError("Permission denied.")

    @staticmethod
    @login_required
    def resolve_summary_contribution_query(root, info, user_id, from_date, to_date):
        user = User.objects.get(pk=user_id)
        if user:
            q = (
                ReportAggregateView.objects.annotate(day=TruncDay("created_at"))
                .filter(reported_by=user, test_flag=False)
                .values("day")
                .annotate(total=Count("report_id"))
                .order_by("day")
            )
            # print(q.query)
            if from_date:
                q = q.filter(created_at__gte=from_date)

            if to_date:
                q = q.filter(created_at__lte=to_date)

            return q
        else:
            raise GraphQLError("User not founded.")
