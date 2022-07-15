import graphene

from pagination import DjangoPaginationConnectionField
from .types import (
    AdminCaseDefinitionQueryType,
    AdminStateDefinitionQueryType,
    CaseDefinitionType,
    CaseType,
    StateDefinitionType,
    StateStepType,
    StateTransitionType,
)
from ..models import Case, CaseDefinition, StateDefinition, StateStep, StateTransition


class Query(graphene.ObjectType):
    cases_query = DjangoPaginationConnectionField(CaseType)
    case_get = graphene.Field(CaseType, id=graphene.UUID(required=True))
    case_definition_get = graphene.Field(
        CaseDefinitionType, id=graphene.ID(required=True)
    )
    admin_case_definition_query = DjangoPaginationConnectionField(
        AdminCaseDefinitionQueryType
    )
    state_definition_get = graphene.Field(
        StateDefinitionType, id=graphene.ID(required=True)
    )
    admin_state_definition_query = DjangoPaginationConnectionField(
        AdminStateDefinitionQueryType
    )
    state_step_get = graphene.Field(StateStepType, id=graphene.ID(required=True))
    admin_state_step_query = graphene.List(
        StateStepType, definition_id=graphene.ID(required=True)
    )

    state_transition_get = graphene.Field(
        StateTransitionType, id=graphene.ID(required=True)
    )
    admin_state_transition_query = graphene.List(
        StateTransitionType, definition_id=graphene.ID(required=True)
    )

    @staticmethod
    def resolve_case_get(root, info, id):
        return Case.objects.get(pk=id)

    @staticmethod
    def resolve_case_definition_get(root, info, id):
        return CaseDefinition.objects.get(pk=id)

    @staticmethod
    def resolve_state_definition_get(root, info, id):
        return StateDefinition.objects.get(pk=id)

    @staticmethod
    def resolve_state_step_get(root, info, id):
        return StateStep.objects.get(pk=id)

    @staticmethod
    def resolve_admin_state_step_query(root, info, definition_id):
        return StateStep.objects.filter(state_definition__id=definition_id)

    @staticmethod
    def resolve_state_transition_get(root, info, id):
        return StateTransition.objects.get(pk=id)

    @staticmethod
    def resolve_admin_state_transition_query(root, info, definition_id):
        return StateTransition.objects.filter(
            from_step__state_definition__id=definition_id
        )
