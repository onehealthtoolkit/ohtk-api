import graphene


class AdminFieldValidationProblem(graphene.ObjectType):
    name = graphene.String(required=True)
    message = graphene.String(required=True)


class AdminValidationProblem(graphene.ObjectType):
    fields = graphene.List(
        graphene.NonNull(AdminFieldValidationProblem), required=False
    )
    message = graphene.String(required=False)
