# AGENTS.md

This file applies to the `ohtk-api` repository. It is the single repo-specific agent guide (setup, architecture, and working rules).

## Repo Focus

`ohtk-api` is the backend for both `ohtk-ms` and `ohtk-mobile`. Most product changes here are contract changes, not isolated backend-only changes.

Before editing, identify:

- which Django app owns the behavior
- whether the change is `public` schema, tenant schema, or both
- whether the change affects GraphQL consumers in web or mobile

## Collaboration And Autonomy

- Default to a lighter-touch collaboration mode than fully autonomous Codex.
- For questions or investigation requests, answer from current code first and do not edit files unless the user explicitly asks for a patch.
- For implementation requests, make the smallest direct patch, but pause and explain before broad cross-repo changes, generated artifact churn, migrations, long-running processes, browser debugging, or dependency installs.
- Ask before expanding scope beyond the named app, schema surface, model, or bug.
- Keep verification narrow and proportionate. Prefer targeted app tests over broad full-suite runs unless the risk justifies it.
- Treat explicit words like "fix", "update", "add", "implement", "commit", and "run" as permission to act within the requested scope.

## Common Commands

Settings module is `podd_api.settings` (the Readme still references the old `config/` path — ignore it). Place any local overrides in `podd_api/local.py`; it is imported at the end of `settings.py` if present.

```bash
# Run the upgraded API locally
python3.12 -m venv .venv                    # first time only; .venv is gitignored
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py runserver 127.0.0.1:8000

# Expose the API at the HTTPS dev host used by ohtk-ms
valet proxy opensur http://127.0.0.1:8000 --secure
# then use https://opensur.test/graphql/ and https://opensur.test/admin/

# Other manage.py commands
python manage.py migrate                    # applies to the public schema + any tenant schemas
python manage.py createsuperuser

# Celery worker (tenant-aware via tenant_schemas_celery)
python -m celery -A podd_api worker -l info

# Local infra (Postgres+PostGIS, Redis) for development
docker compose -f docker/docker-compose.yml up db redis

# Tests — both runners are wired up
python manage.py test <dotted.path>         # Django runner (used in Readme examples)
pytest <path>                               # reads pytest.ini; same DJANGO_SETTINGS_MODULE
pytest reports/tests/test_report_type.py::ReportTypeTests::test_xxx   # single test

# Fixtures (per-app yaml fixtures)
./manage.py dumpdata --format=yaml accounts > accounts/fixtures/accounts.yaml
./manage.py loaddata --format=yaml accounts
```

After the Django 4.2 / Python 3.12 upgrade, do not trust an old `ohtk-api` pyenv env for client schema work: it may still serve the pre-upgrade GraphQL SDL. Use the local `.venv` above or another Python 3.12 environment installed from current `requirements.txt`. The web client expects HTTPS through `opensur.test`, so keep the Django server on `127.0.0.1:8000` and let Valet terminate TLS.

The database backend is `django_tenants.postgresql_backend` wrapping PostGIS (`ORIGINAL_BACKEND = django.contrib.gis.db.backends.postgis`) — the DB cluster must have PostGIS available, not plain Postgres. `DATABASE_ROUTERS` is `TenantSyncRouter`, so `migrate` knows which app belongs to which schema.

Workspace FAO/Overmind local stack: see the workspace-root `AGENTS.md` and `Procfile.local` (`DB_NAME=ohtk_staging_poc_20260505` for the copied staging DB).

## Architecture

### Multi-tenancy (django-tenants)

`TenantMainMiddleware` resolves the incoming hostname to a row in `tenants_domain → tenants_client` and switches the Postgres `search_path` to that client's schema for the request. Apps are split into:

- `SHARED_APPS` (settings.py) — live in the `public` schema. Includes `accounts`, `tenants`, plus app code that is *also* in `TENANT_APPS` because the models need to exist in both places.
- `TENANT_APPS` — per-tenant data (`reports`, `cases`, `observations`, `outbreaks`, `summaries`, `threads`, `notifications`, `common`, `oauth2_provider`, `accounts`).

`SHOW_PUBLIC_IF_NO_TENANT_FOUND = True` means unmapped hosts fall through to the public schema rather than 404 — relevant when writing tests or hitting localhost. When adding a new app, decide whether it stores tenant-scoped data and add it to the correct tuple; `INSTALLED_APPS` is built as `SHARED_APPS + (TENANT_APPS - SHARED_APPS)`.

### GraphQL is the primary API surface

The only non-admin HTTP endpoint is `/graphql/` (`FileUploadGraphQLView` wrapped in `jwt_cookie` + `csrf_exempt`). The root schema in `podd_api/schema.py` composes per-app `Query` and `Mutation` classes via multiple inheritance — each app exposes its schema from `<app>/schema/__init__.py` (`query.py` + `mutation.py`, with individual mutations under `<app>/schema/mutations/`). When adding a new app's GraphQL types, follow the same pattern and add it to both base classes in `podd_api/schema.py`.

REST endpoints are narrow exceptions: `api/userinfo/`, `api/servers/`, OAuth2 under `/o/`, and i18n-prefixed Excel exports under `summaries/views.py`.

### Auth stack

Three authentication backends stacked in order: `accounts.backends.MyJSONWebTokenBackend` (graphql-jwt, customized), `oauth2_provider.backends.OAuth2Backend`, and Django's `ModelBackend`. JWT is cookie-delivered (`JWT_COOKIE_SAMESITE=None`, `SECURE=True`) with a 30-minute access token and 14-day refresh. The GraphQL endpoint exposes `tokenAuth`, `verifyToken`, `refreshToken`, `revokeToken`, plus the cookie-clearing mutations directly on the root `Mutation`.

### Background work

Celery broker is Redis (`CELERY_BROKER_URL`). The `TenantAwareCeleryApp` from `tenant_schemas_celery` wraps `CeleryApp`, so tasks pickle their tenant context — when enqueueing, remember the worker will re-enter the caller's schema. Tasks live in `<app>/tasks.py` and are auto-discovered.

Channels + Redis is configured (`ASGI_APPLICATION = podd_api.asgi.application`) but the only consumer currently wired is under `reports/` (`consumers.py`, `routing.py`).

### Model conventions

- `common.models.BaseModel` adds `created_at`, `updated_at`, `deleted_at`, and overrides `delete()` to default to a *soft* delete (`deleted_at = now()`). Pass `hard=True` to actually delete. Use `BaseModelManager` to auto-filter soft-deleted rows; subclasses that need to see deleted rows should expose a separate manager.
- `AUTH_USER_MODEL = accounts.User`. `AuthorityUser` (in `accounts/models.py`) is the per-tenant user tied to an `Authority` — the hierarchical org unit used across reports/cases/observations. Tests under `reports/tests/base_testcase.py` set up a canonical Thailand→BKK→Jatujak / Chiangmai authority tree you can reuse.

### File storage

`USE_S3=True` switches `DEFAULT_FILE_STORAGE` to `common.storage.S3MediaStorage` (and mirrors to easy-thumbnails). Locally, files land in `medias/` and are served via the dev URL patterns. Thumbnails are pre-configured in `THUMBNAIL_ALIASES` for user avatars, report images, observation record images, and thread attachments.

### CI / deploy

`.github/workflows/build.yml` builds the Docker image on push to `main` (and related publish targets). The Dockerfile extends a python-gdal-magic base because GDAL is required for the GIS stack. The entrypoint runs `collectstatic`, optional gated `migrate_schemas` when `RUN_MIGRATIONS` is truthy, optional superuser creation, then **daphne** ASGI (`podd_api.asgi:application`). Shared staging/production should migrate out-of-band, not on every boot.

## Change Rules

- Keep changes inside the owning app unless the work truly crosses app boundaries.
- Prefer extending the existing per-app schema layout under `*/schema/` instead of adding ad hoc endpoints.
- Keep migrations focused and intentional. Do not mix unrelated schema cleanup into feature work.
- Respect soft-delete behavior from `common.models.BaseModel`; do not introduce hard deletes casually.
- Treat tenant/domain resolution, permissions, and auth flows as high-risk areas and verify them explicitly.
- Do not hand-edit cache or local runtime artifacts.

## Files To Avoid Editing By Hand

- `.pytest_cache/`
- `medias/` unless the task is specifically about local uploaded files
- `docker/data/`

Generated migration files are expected when models change, but they should be reviewed carefully before finishing.

## Common Change Patterns

### GraphQL changes

- Follow the existing app pattern: types, queries, and mutations live under `<app>/schema/`.
- If you add a new app-level query or mutation surface, make sure it is composed into [podd_api/schema.py](podd_api/schema.py).
- Assume schema changes may require follow-up work in `ohtk-ms` and `ohtk-mobile`.

### Model changes

- Check whether the model belongs in shared apps, tenant apps, or both before changing migrations or settings.
- Review manager behavior, soft-delete behavior, and any tenant assumptions in tests.

### Background jobs

- Keep Celery tasks tenant-safe. Changes to task inputs or side effects should be tested with tenant context in mind.

## Verification

Use the narrowest meaningful validation for the area you changed:

- targeted `pytest` for the touched app
- targeted `python manage.py test` when the existing tests are organized that way
- broader test coverage when touching auth, tenants, schema composition, or shared model behavior

If models changed, also verify migrations are in good shape.

## Handoff Notes

Final notes for work in this repo should call out:

- whether the change affects `ohtk-ms`
- whether the change affects `ohtk-mobile`
- what verification was run
- any tenant/auth/data migration risks that remain
