import graphene
from graphql_jwt.decorators import login_required

from reports.models import ReportType
from reports.types import ReportTypeType


class Query(graphene.ObjectType):
    my_report_types = graphene.List(ReportTypeType)

    @staticmethod
    @login_required
    def resolve_my_report_types(root, info):
        user = info.context.user
        authority = user.authorityuser.authority
        return ReportType.filter_by_authority(authority)
