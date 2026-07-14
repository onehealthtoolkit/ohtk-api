from accounts.models import Configuration
from accounts.village_capability import FEATURE_DISABLED_VALUE, FEATURE_ENABLED_VALUE


INTEGRATION_ENABLED_KEY = "integrations.enabled"
AI_ENABLED_KEY = "integrations.ai_enabled"
RISK_EVALUATOR_ENABLED_KEY = "integrations.risk_evaluator_enabled"
CLUSTER_DETECTOR_ENABLED_KEY = "integrations.cluster_detector_enabled"
AI_DEFAULT_COMMENT_OWNER_USER_ID_KEY = "integrations.ai_default_comment_owner_user_id"
DASHBOARD_RISK_WINDOW_DAYS_KEY = "integrations.dashboard_risk_window_days"

DEFAULT_DASHBOARD_RISK_WINDOW_DAYS = 7
MAX_DASHBOARD_RISK_WINDOW_DAYS = 365


def _get_value(key, default=""):
    configuration = Configuration.objects.filter(key=key).first()
    if not configuration:
        return default
    return configuration.value


def _is_enabled(key):
    # Default on when unset so already-deployed integration clients keep working
    # until a tenant admin explicitly disables the policy keys.
    return _get_value(key, FEATURE_ENABLED_VALUE) == FEATURE_ENABLED_VALUE


def _set_value(key, value):
    configuration = Configuration._base_manager.filter(key=key).first()
    if configuration:
        configuration.value = str(value)
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration

    return Configuration.objects.create(key=key, value=str(value))


def _set_enabled(key, enabled):
    return _set_value(key, FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE)


def get_integration_policy():
    raw_window_days = _get_value(
        DASHBOARD_RISK_WINDOW_DAYS_KEY,
        str(DEFAULT_DASHBOARD_RISK_WINDOW_DAYS),
    )
    try:
        dashboard_risk_window_days = int(raw_window_days)
    except (TypeError, ValueError):
        dashboard_risk_window_days = DEFAULT_DASHBOARD_RISK_WINDOW_DAYS

    return {
        "integration_enabled": _is_enabled(INTEGRATION_ENABLED_KEY),
        "ai_enabled": _is_enabled(AI_ENABLED_KEY),
        "risk_evaluator_enabled": _is_enabled(RISK_EVALUATOR_ENABLED_KEY),
        "cluster_detector_enabled": _is_enabled(CLUSTER_DETECTOR_ENABLED_KEY),
        "ai_default_comment_owner_user_id": _get_value(
            AI_DEFAULT_COMMENT_OWNER_USER_ID_KEY,
            "",
        ),
        "dashboard_risk_window_days": dashboard_risk_window_days,
    }


def set_integration_policy(
    *,
    integration_enabled,
    ai_enabled,
    risk_evaluator_enabled,
    cluster_detector_enabled,
    ai_default_comment_owner_user_id,
    dashboard_risk_window_days,
):
    _set_enabled(INTEGRATION_ENABLED_KEY, integration_enabled)
    _set_enabled(AI_ENABLED_KEY, ai_enabled)
    _set_enabled(RISK_EVALUATOR_ENABLED_KEY, risk_evaluator_enabled)
    _set_enabled(CLUSTER_DETECTOR_ENABLED_KEY, cluster_detector_enabled)
    _set_value(
        AI_DEFAULT_COMMENT_OWNER_USER_ID_KEY,
        ai_default_comment_owner_user_id or "",
    )
    _set_value(DASHBOARD_RISK_WINDOW_DAYS_KEY, dashboard_risk_window_days)
    return get_integration_policy()


# Feature keys accepted by assert_integration_feature_enabled.
FEATURE_AI = "ai"
FEATURE_RISK_EVALUATOR = "risk_evaluator"
FEATURE_CLUSTER_DETECTOR = "cluster_detector"

_FEATURE_POLICY_KEYS = {
    FEATURE_AI: ("ai_enabled", "AI integration is disabled for this tenant."),
    FEATURE_RISK_EVALUATOR: (
        "risk_evaluator_enabled",
        "Risk evaluator integration is disabled for this tenant.",
    ),
    FEATURE_CLUSTER_DETECTOR: (
        "cluster_detector_enabled",
        "Cluster detector integration is disabled for this tenant.",
    ),
}


class IntegrationPolicyDenied(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def assert_integration_feature_enabled(feature=None):
    """
    Enforce tenant integration policy for REST/webhook entry points.

    Always requires integrations.enabled. Optional feature-specific toggles:
    ai, risk_evaluator, cluster_detector.
    """
    policy = get_integration_policy()
    if not policy["integration_enabled"]:
        raise IntegrationPolicyDenied(
            "integration_disabled",
            "Integrations are disabled for this tenant.",
        )
    if feature is None:
        return policy
    try:
        policy_key, message = _FEATURE_POLICY_KEYS[feature]
    except KeyError as exc:
        raise ValueError(f"Unknown integration feature: {feature}") from exc
    if not policy[policy_key]:
        raise IntegrationPolicyDenied(f"{feature}_disabled", message)
    return policy
