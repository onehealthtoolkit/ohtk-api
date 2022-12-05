import graphene


class AdminObservationDefinitionCreateMutation(graphene.Mutation):
    """
    use to create a new observation definition
    """

    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        register_form_definition = graphene.JSONString(required=True)
        title_template = graphene.String(required=True)
        description_template = graphene.String(required=True)
        identity_template = graphene.String(required=True)

    def mutate(
        self,
        info,
        name,
        description,
        register_form_definition,
        title_template,
        description_template,
        identity_template,
    ):
        pass


class AdminObservationDefinitionUpdateMutation(graphene.Mutation):
    pass


class AdminObservationDefinitionDeleteMutation(graphene.Mutation):
    pass
