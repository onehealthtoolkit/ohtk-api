#### Full Documentation [here](https://onehealthtoolkit.github.io/ohtk-docs/ohtk-api/)

## Quick Start

### What you'll need
- python 3.8 or higher
- pip
- [Laravel Valet](https://laravel.com/docs/9.x/valet) (if using a proxy over HTTP)

### Install
Get the latest version of ohtk-api

```git clone https://github.com/onehealthtoolkit/ohtk-api.git```

```cd ~/ohtk-api```

It is recommended that you install the required packages via a virtual environment (such as [venv](https://docs.python.org/3/library/venv.html)): 

```python -m venv pickavirtualenvname```

```source pickavirtualenvname/bin/activate```

Install dependencies

```pip install -r requirements.txt```

### Start a Postgres Server
You can use the [Postgres MacOS app](https://postgresapp.com/) for an easy-to-use interface.

### Update database settings (config/settings.py)
```DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'database name',
        'USER': 'username',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '',
    }
}
```

### Run Django manage.py commands

```python ./manage.py migrate```

```python ./manage.py createsuperuser```

### Test data commands

```./manage.py dumpdata --format=yaml accounts> accounts/fixtures/accounts.yaml```

```./manage.py loaddata --format=yaml accounts```

### Start Local Server

``` python ./manage.py runserver```

[http://127.0.0.1:8000](http://127.0.0.1:8000)

### Start Proxy (using [Laravel Valet](https://laravel.com/docs/9.x/valet))

```valet proxy opensur http://127.0.0.1:8000 --secure```

Navigate to [https://opensur.test/admin/](https://opensur.test/admin/) or [http://opensur.test/graphql/](http://opensur.test/graphql/)

Remove a proxy using the unproxy command:

```
valet unproxy opensur
```

### Make sure everthing is working with these test commands

```
./manage.py test accounts.tests.test_admin_authority_user_crud.AdminAuthorityUserTests.test_update_with_error
./manage.py test reports.tests.test_admin_category_crud.AdminCategoryTests.test_simple_query
./manage.py test cases.tests.test_admin_state_definition_crud.AdminStateDefinitionTests.test_update_with_error
```

#### By this point you should be ready to install the [OHTK Management System](https://github.com/onehealthtoolkit/ohtk-ms)

---------

### Django Tenants Overview

OHTK API uses [Django Tenants](https://django-tenants.readthedocs.io/en/latest/use.html)

By default, if there are no any record config in tenants_client and tenants_domain table then every incoming request will resolve to public database schema.

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
