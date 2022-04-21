## Tenant

by default, If there are no any record config in tenants_client and tenants_domain table then every incoming request will resolve to public database schema.

#### references
* https://django-tenants.readthedocs.io/en/latest/use.html

### To create a new tenant
* create a record in tenants_client
* create mapping from subdomain name to tenants_client in tenants_domain

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