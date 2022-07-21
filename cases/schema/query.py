import graphene
from graphql_jwt.decorators import login_required

from pagination import DjangoPaginationConnectionField
from .types import (
    AdminCaseDefinitionQueryType,
    AdminStateDefinitionQueryType,
    CaseDefinitionType,
    CaseType,
    StateDefinitionType,
    StateStepType,
    StateTransitionType,
    DeepStateDefinitionType,
    AdminNotificationTemplateAuthorityType,
)
from ..models import (
    Case,
    CaseDefinition,
    StateDefinition,
    StateStep,
    StateTransition,
    NotificationTemplate,
)


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

    deep_state_definition_get = graphene.Field(
        DeepStateDefinitionType, id=graphene.ID(required=True)
    )
    admin_notification_template_authority_query = graphene.List(
        AdminNotificationTemplateAuthorityType,
        report_type_id=graphene.ID(required=True),
    )

    @staticmethod
    @login_required
    def resolve_case_get(root, info, id):
        return Case.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_case_definition_get(root, info, id):
        return CaseDefinition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_state_definition_get(root, info, id):
        return StateDefinition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_state_step_get(root, info, id):
        return StateStep.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_state_step_query(root, info, definition_id):
        return StateStep.objects.filter(state_definition__id=definition_id)

    @staticmethod
    @login_required
    def resolve_state_transition_get(root, info, id):
        return StateTransition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_state_transition_query(root, info, definition_id):
        return StateTransition.objects.filter(
            from_step__state_definition__id=definition_id
        )

    @staticmethod
    @login_required
    def resolve_deep_state_definition_get(root, info, id):
        return StateDefinition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_notification_template_authority_query(root, info, report_type_id):
        user = info.context.user
        if user.is_authority_user():
            notifications = NotificationTemplate.objects.filter(
                report_type_id=report_type_id
            ).raw(
                """select nt.id, nt.name, an.to
                   from cases_notificationtemplate nt left join
                        cases_authoritynotification an on nt.id = an.template_id and an.authority_id = %s
                   """,
                [user.authorityuser.authority.id],
            )
            return [
                {
                    "notification_template_id": n.id,
                    "notification_template_name": n.name,
                    "to": n.to,
                }
                for n in notifications
            ]
        else:
            return []
