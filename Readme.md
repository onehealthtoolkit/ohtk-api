## Tenant

by default, If there are no any record config in tenants_client and tenants_domain table then every incoming request will resolve to public database schema.

#### references

- https://django-tenants.readthedocs.io/en/latest/use.html

### To create a new tenant

- create a record in tenants_client
- create mapping from subdomain name to tenants_client in tenants_domain

```
┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │
│ tenants_client  │        ╱│ tenants_domain  │
│                 │──────┼──│                 │
│                 │        ╲│                 │
└─────────────────┘         └─────────────────┘
         │                           │
         └────┐                      └─┐
              │                        │
         .─────────.              .─────────.
        (schema_name)            (   name    )
         `─────────'              `─────────'
```

Setting Up the Django Admin ref: https://realpython.com/lessons/setting-up-admin/

## Django

- pip install -r requirements.txt
- python ./manage.py migrate
- python ./manage.py createsuperuser

## Data test command

- ./manage.py dumpdata --format=yaml accounts> accounts/fixtures/accounts.yaml
- ./manage.py loaddata --format=yaml accounts

# Admin

- python ./manage.py runserver
- http://opensur.test/admin/
- http://opensur.test/graphql/
  ใน django url ต้องลงท้ายด้วย slash เสมอ

#### Valet references

https://laravel.com/docs/master/valet

# Proxy over HTTP...

```
valet proxy opensur http://127.0.0.1:8000
```

# Remove a proxy using the unproxy command:

```
valet unproxy opensur
```

# Example Test command

```
./manage.py test accounts.test.test_admin_authority_user_crud.AdminAuthorityUserTests.test_update_with_error
./manage.py test reports.test.test_admin_category_crud.AdminCategoryTests.test_simple_query
```
