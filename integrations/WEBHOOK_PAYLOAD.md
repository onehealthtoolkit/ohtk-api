# Webhook tenant API URL

Both `report.submitted` and `ai.evaluation_requested` include
`tenant.apiBaseUrl`, for example `https://tot.api.lahis.ohtk.org`.

The API resolves this HTTPS origin from the tenant's primary `Domain` record
in the public schema. It does not derive it from the schema name, request Host,
or a non-primary alias. Without a registered primary domain the field is `null`;
consumers should reject unresolved routing rather than fall back to another tenant.

Webhook `links` remain relative paths. Consumers should validate the webhook
signature and their allowed API hosts, then use this origin for OAuth, incident
reads and result callbacks. Cache tokens separately per tenant/API origin.

This is an additive payload field, not a GraphQL or database schema change.
Dashboard and mobile clients require no changes. External AI consumers must
read the new field; it does not repair invalid OAuth credentials. Existing
persisted event payloads are not backfilled by this code change.
