import graphene
from graphene_django import DjangoObjectType

from accounts.schema.types import AuthorityType
from graphene.types.generic import GenericScalar
from cases.models import (
    Case,
    CaseDefinition,
    StateDefinition,
    StateStep,
    StateTransition,
    CaseState,
    CaseStateTransition,
)
from common.types import AdminValidationProblem
from reports.schema.types import IncidentReportType


class StateDefinitionType(DjangoObjectType):
    class Meta:
        model = StateDefinition
        fields = ["id", "name", "is_default"]


# CaseDefinitionType
class CaseDefinitionType(DjangoObjectType):
    class Meta:
        model = CaseDefinition
        fields = [
            "id",
            "report_type",
            "description",
            "condition",
            "is_active",
        ]


class AdminCaseDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = CaseDefinition
        fields = ("id", "report_type", "description", "condition")
        filter_fields = {
            "description": ["istartswith", "exact"],
        }


class AdminCaseDefinitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = CaseDefinition


class AdminCaseDefinitionCreateProblem(AdminValidationProblem):
    pass


class AdminCaseDefinitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminCaseDefinitionCreateSuccess,
            AdminCaseDefinitionCreateProblem,
        )


class AdminCaseDefinitionUpdateSuccess(graphene.ObjectType):
    case_definition = graphene.Field(CaseDefinitionType)


class AdminCaseDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminCaseDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminCaseDefinitionUpdateSuccess,
            AdminCaseDefinitionUpdateProblem,
        )


# StateDefinitionType
class AdminStateDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = StateDefinition
        fields = ("id", "name", "is_default")
        filter_fields = {
            "name": ["istartswith", "exact"],
        }


class AdminStateDefinitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = StateDefinition


class AdminStateDefinitionCreateProblem(AdminValidationProblem):
    pass


class AdminStateDefinitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateDefinitionCreateSuccess,
            AdminStateDefinitionCreateProblem,
        )


class AdminStateDefinitionUpdateSuccess(graphene.ObjectType):
    state_definition = graphene.Field(StateDefinitionType)


class AdminStateDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminStateDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateDefinitionUpdateSuccess,
            AdminStateDefinitionUpdateProblem,
        )


# StateStepType
class StateStepType(DjangoObjectType):
    state_definition = graphene.Field(StateDefinitionType)

    class Meta:
        model = StateStep
        fields = ["id", "name", "is_start_state", "is_stop_state", "state_definition"]


class AdminStateStepCreateSuccess(DjangoObjectType):
    class Meta:
        model = StateStep


class AdminStateStepCreateProblem(AdminValidationProblem):
    pass


class AdminStateStepCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateStepCreateSuccess,
            AdminStateStepCreateProblem,
        )


class AdminStateStepUpdateSuccess(graphene.ObjectType):
    state_step = graphene.Field(StateStepType)


class AdminStateStepUpdateProblem(AdminValidationProblem):
    pass


class AdminStateStepUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateStepUpdateSuccess,
            AdminStateStepUpdateProblem,
        )


# StateTransitionType
class StateTransitionType(DjangoObjectType):
    form_definition = GenericScalar()

    class Meta:
        model = StateTransition


class AdminStateTransitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = StateTransition


class AdminStateTransitionCreateProblem(AdminValidationProblem):
    pass


class AdminStateTransitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateTransitionCreateSuccess,
            AdminStateTransitionCreateProblem,
        )


class AdminStateTransitionUpdateSuccess(graphene.ObjectType):
    state_transition = graphene.Field(StateTransitionType)


class AdminStateTransitionUpdateProblem(AdminValidationProblem):
    pass


class AdminStateTransitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminStateTransitionUpdateSuccess,
            AdminStateTransitionUpdateProblem,
        )


class CaseStateTransitionType(DjangoObjectType):
    transition = graphene.Field(StateTransitionType, required=True)
    form_data = graphene.JSONString

    class Meta:
        model = CaseStateTransition
        fields = ["id", "created_at", "transition", "form_data", "created_by"]


class DeepStateTransitionType(DjangoObjectType):
    from_step = graphene.Field(StateStepType)
    to_step = graphene.Field(StateStepType)
    form_definition = graphene.JSONString

    class Meta:
        model = StateTransition
        fields = ["id", "from_step", "to_step", "form_definition"]


class DeepStateStepType(DjangoObjectType):
    to_transitions = graphene.List(DeepStateTransitionType)

    class Meta:
        model = StateStep
        fields = ["id", "name", "is_start_state", "is_stop_state", "to_transitions"]

    def resolve_to_transitions(self, info):
        return self.to_transitions.all()


class DeepStateDefinitionType(DjangoObjectType):
    statestep_set = graphene.List(DeepStateStepType)

    class Meta:
        model = StateDefinition
        fields = ["id", "name", "is_default", "statestep_set"]


class CaseStateType(DjangoObjectType):
    state = graphene.Field(DeepStateStepType, required=True)
    transition = graphene.Field(CaseStateTransitionType, required=True)

    class Meta:
        model = CaseState
        fields = ["id", "state", "transition"]


class CaseType(DjangoObjectType):
    state_definition = graphene.Field(DeepStateDefinitionType)
    report = graphene.Field(IncidentReportType)
    authorities = graphene.List(AuthorityType)
    states = graphene.List(CaseStateType)

    class Meta:
        model = Case
        fields = [
            "id",
            "report",
            "state_definition",
            "description",
            "authorities",
        ]
        filter_fields = {
            "report__created_at": ["lte", "gte"],
            "report__relevant_authorities__id": ["in"],
        }

    def resolve_states(root, info):
        return root.casestate_set.all()

    def resolve_authorities(root, info):
        return root.authorities.all()
