import graphene
import graphql_jwt
from accounts.schema import Query as AccountsQuery
from accounts.schema import Mutation as AccountsMutation
from threads.schema import Query as ThreadQuery
from threads.schema import Mutation as ThreadMutation
from reports.schema import Query as ReportsQuery
from reports.schema import Mutation as ReportsMutation
from cases.schema import Query as CasesQuery
from cases.schema import Mutation as CasesMutation
from notifications.schema import Query as NotificationsQuery
from notifications.schema import Mutation as NotificationsMutation
from summaries.schema import Query as SummariesQuery
from outbreaks.schema import Query as OutbreaksQuery
from outbreaks.schema import Mutation as OutbreaksMutation
from observations.schema import Query as ObservationsQuery
from observations.schema import Mutation as ObservationsMutation


class Query(
    AccountsQuery,
    ReportsQuery,
    CasesQuery,
    NotificationsQuery,
    SummariesQuery,
    ThreadQuery,
    OutbreaksQuery,
    ObservationsQuery,
    graphene.ObjectType,
):
    health_check = graphene.String(default_value="ok")


class Mutation(
    AccountsMutation,
    ReportsMutation,
    CasesMutation,
    NotificationsMutation,
    ThreadMutation,
    OutbreaksMutation,
    ObservationsMutation,
    graphene.ObjectType,
):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    revoke_token = graphql_jwt.Revoke.Field()
    delete_token_cookie = graphql_jwt.DeleteJSONWebTokenCookie.Field()
    delete_refresh_token_cookie = graphql_jwt.DeleteRefreshTokenCookie.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
