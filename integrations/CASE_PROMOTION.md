# External integration: promote a report to a case

`POST /api/integrations/v1/reports/{reportId}/promote-case`

Call this endpoint on the report's tenant API host. It uses the same service
OAuth channel as integration comments and risk assessments. The dashboard/mobile
GraphQL `promoteToCase` mutation continues to use human user permissions.

## Authorization

- A valid OAuth2 bearer token from a confidential client-credentials application.
- An active Integration Client linked to that application in the selected tenant.
- Integration Client scope `case:promote` ("Promote cases" in the dashboard).
- Tenant integration and AI integration policy enabled, using the existing
  `integrations.enabled` and `integrations.ai_enabled` policy checks. The same
  existing policy defaults apply; this endpoint adds no policy setting.
- The token must have no human user. Dashboard sessions and human-bound OAuth
  tokens do not authorize this endpoint.

Integration access is tenant-wide, consistent with the existing integration
contract. This endpoint does not apply human officer authority subtree rules.
It cannot access another tenant's reports or accept another tenant's token.

## Request

```bash
curl --request POST \
  "$TENANT_API_URL/api/integrations/v1/reports/$REPORT_ID/promote-case" \
  --header "Authorization: Bearer $ACCESS_TOKEN" \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: ai-promote-001' \
  --data '{"externalActionId":"ai-promote-001"}'
```

`externalActionId` is an optional string up to 200 characters. It is also the
idempotency key when the header is absent. With an `Idempotency-Key` header, an
empty JSON object is sufficient. A nonempty key of at most 200 characters is
required. No other body fields are accepted.

## Success — HTTP 200

```json
{
  "schemaVersion": "2026-06-02",
  "status": "accepted",
  "case": {
    "id": "case-uuid",
    "reportId": "report-uuid"
  },
  "alreadyPromoted": false
}
```

Promotion uses the existing case workflow: report-specific mapping or default
workflow, initial state, relevant authorities, report case link and promotion
notification signal. A workflow with a start state must be configured.
The promotion signal runs after the database transaction commits, so rolled-back
promotions do not enqueue notifications and workers can read the committed case.

If the report already has a case, a request with a new key returns that case
with `alreadyPromoted: true`. It does not reopen, reset or notify again for the
existing case. Retrying the same key, report and JSON payload returns the exact
original response, including the original `alreadyPromoted` value.

Reusing a key with another report or a different JSON payload returns HTTP 409.
Keys are scoped to the Integration Client and `case.promote` action. Promotion,
initial case state, report link, successful audit and saved response commit in
one database transaction. A report row lock serializes promotions through this
endpoint, including calls with different keys. Existing GraphQL promotion is
unchanged. Authorization and tenant policy are checked on every request,
including replays.

## Errors

Errors use `{"error":{"code":"...","message":"..."}}`.

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_json` | Body is malformed JSON or is not an object. |
| 400 | `invalid_payload` | Unknown body fields, invalid action ID, missing/oversized key. |
| 401 | `oauth_required` | Missing, invalid, expired or wrong-tenant bearer token. |
| 403 | `tenant_denied` | Public schema cannot use integration endpoints. |
| 403 | `integration_client_denied` | Inactive/unlinked client or unsupported OAuth application. |
| 403 | `service_identity_denied` | OAuth token has a human user. |
| 403 | `scope_denied` | Integration Client lacks `case:promote`. |
| 403 | `integration_disabled` | Tenant integrations are disabled. |
| 403 | `ai_disabled` | Tenant AI integration is disabled. |
| 404 | `report_not_found` | Report is absent or soft-deleted in this tenant. |
| 405 | — | Method is not POST. |
| 409 | `idempotency_conflict` | Same key was used with another report/payload. |
| 409 | `case_workflow_unavailable` | Case workflow cannot initialize. Configure it, then retry. |

Accepted, replayed and rejected requests after active-client identification are
recorded in `IntegrationActionLog` with action `case.promote` and required scope
`case:promote`. Authorization headers are redacted. Failed transactions do not
consume the idempotency key.

## Client impact

No GraphQL schema, database migration, dashboard or mobile change is required.
External AI clients can call this REST endpoint after API deployment and after
their tenant/client configuration permits promotion. This source change does
not enable integrations or modify credentials on any server.
