import graphene
import graphql_jwt
from accounts.schema import Query as AccountsQuery
from accounts.schema import Mutation as AccountsMutation
from reports.schema import Query as ReportsQuery
from reports.schema import Mutation as ReportsMutation


class Query(AccountsQuery, ReportsQuery, graphene.ObjectType):
    hello = graphene.String(default_value="Hi!")


class Mutation(AccountsMutation, ReportsMutation, graphene.ObjectType):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    revoke_token = graphql_jwt.Revoke.Field()
    delete_token_cookie = graphql_jwt.DeleteJSONWebTokenCookie.Field()
    delete_refresh_token_cookie = graphql_jwt.DeleteRefreshTokenCookie.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
