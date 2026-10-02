# A very opinionated style guide

1) Use FBVs rather than CBVs
2) Each view must be annotated with:
   - `@api_view()`
   - `@throttle_classes()`
   - `@permission_classes()`
3) Each view must end in `_view`
4) Resource services must use `authorizer` from `website.auth.permissions.authorizer`. Policies compose the checks centrally; views must not assemble permission contexts or choose checks. The old `resource_access` import is only a compatibility adapter for excluded search code. See `../authorization-access-api.md`.
5) Use custom `method_dispatcher` to dispatch to appropriate `view` functions based on `http method`
6) Each new exception must end with `Error` and derive from `IDriveException`
7) Common code, that does NOT interact with `Models` directly should live in `core` package
8) Data-loading queries belong in `queries`; predicates that decide resource visibility belong with the policy in `auth/permissions`.
9) All ORM queries that modify anything and depend on only 1 model must live in `models` package
10) All ORM queries that modify anything and depend on multiple models must live in `services` package
11) **NEVER** call `save()` or `update()` outside of `models` or `services`
12) All instances of calling `bulk_update` must be heavily documented and used only when **absolutely** necessary
13) Please use camel_case for variables and method names
14) Classes MUST start with a big letter
15) use camel_case in json responses
8) # todo
