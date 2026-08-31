class IntegrationScope:
    INCIDENT_READ = "incident:read"
    CENSUS_READ = "census:read"
    CLUSTER_READ_INPUTS = "cluster:read_inputs"
    CLUSTER_WRITE_RESULT = "cluster:write_result"
    AI_READ_REPORT = "ai:read_report"
    AI_READ_IMAGES = "ai:read_images"
    AI_CREATE_COMMENT = "ai:create_comment"
    CASE_PROMOTE = "case:promote"
    RISK_UPDATE = "risk:update"

    CHOICES = (
        (INCIDENT_READ, "Read incidents"),
        (CENSUS_READ, "Read census"),
        (CLUSTER_READ_INPUTS, "Read cluster inputs"),
        (CLUSTER_WRITE_RESULT, "Write cluster results"),
        (AI_READ_REPORT, "AI read reports"),
        (AI_READ_IMAGES, "AI read report images"),
        (AI_CREATE_COMMENT, "AI create comments"),
        (CASE_PROMOTE, "Promote cases"),
        (RISK_UPDATE, "Update risk"),
    )

    CODES = {code for code, _label in CHOICES}


class IntegrationEventType:
    REPORT_SUBMITTED = "report.submitted"
    FOLLOWUP_SUBMITTED = "followup.submitted"
    CASE_PROMOTED = "case.promoted"
    CASE_STATE_CHANGED = "case.state_changed"
    CLUSTER_EVALUATION_REQUESTED = "cluster.evaluation_requested"
    RISK_EVALUATION_REQUESTED = "risk.evaluation_requested"
    AI_EVALUATION_REQUESTED = "ai.evaluation_requested"

    CHOICES = (
        (REPORT_SUBMITTED, "Report submitted"),
        (FOLLOWUP_SUBMITTED, "Followup submitted"),
        (CASE_PROMOTED, "Case promoted"),
        (CASE_STATE_CHANGED, "Case state changed"),
        (CLUSTER_EVALUATION_REQUESTED, "Cluster evaluation requested"),
        (RISK_EVALUATION_REQUESTED, "Risk evaluation requested"),
        (AI_EVALUATION_REQUESTED, "AI evaluation requested"),
    )

    CODES = {code for code, _label in CHOICES}


SECRET_KEY_PARTS = (
    "apikey",
    "authorization",
    "bearer",
    "clientkey",
    "clientsecret",
    "credential",
    "privatekey",
    "password",
    "secret",
    "signature",
    "signingkey",
    "token",
)


def normalize_secret_key_name(key):
    return "".join(char for char in str(key).lower() if char.isalnum())


def is_secret_key_name(key):
    normalized = normalize_secret_key_name(key)
    return any(part in normalized for part in SECRET_KEY_PARTS)


IDEMPOTENCY_UNIQUENESS = "(integration_client, action_type, key)"

AI_EVALUATION_SCHEMA_VERSION = "2026-08-31"
AI_SUMMARY_PURPOSE = "summary"
AI_SUMMARY_DEBOUNCE_SECONDS = 60
AI_SUMMARY_USER_PROMPT_MAX_LENGTH = 2000
AI_SUMMARY_PROMPT_PREVIEW_LENGTH = 120
