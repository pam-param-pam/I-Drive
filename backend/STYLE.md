# Backend conventions

Use the existing module's conventions and keep transport, authorization, queries and domain mutation responsibilities explicit.

- Use function-based DRF API views. Apply the appropriate method, authentication/permission and throttle decorators. New view names should end in `_view`.
- Views parse inputs and construct typed principals/credentials. Domain services select the action; request data must not select weaker checks.
- Use `permissions.authorize(ResourceAction.NAME, ...)` from `website.auth.permissions.engine` for resource authorization. Each action has one policy in `policies.py`. See [authorization-access-api.md](../authorization-access-api.md).
- Put database loading in `queries`, permission decisions and listing predicates in `auth/permissions`, and domain mutations in `services`. Background orchestration belongs in `tasks`.
- File/folder serializers format display projections loaded explicitly through `queries.display`; serializers must not resolve hierarchy or call services. Load related display data before formatting other models.
- Mutations validate current rows under the applicable transaction, owner barrier and resource locks. Use existing locked service cores for accepted namespace work.
- ORM writes also occur in task orchestration, derived-state tasks and internal bootstrap/maintenance paths. Do not impose a blanket ban inconsistent with those boundaries; keep their authority and transaction behavior explicit.
- Use `core` for shared utilities that do not own domain-model mutation.
- Python functions and variables use `snake_case`; classes use `PascalCase`. Existing JSON contracts contain both camelCase and snake_case. Preserve their field names unless deliberately changing the API and its consumers.
- Domain error classes derive from `IDriveException`; follow the existing error naming and response contracts.
- Use `bulk_update` where bounded batches need it, documenting lock ownership and why bypassing model save hooks is safe.
- Keep durable work and required derived-state changes in the domain transaction. Register best-effort WebSocket delivery after commit.

[File/folder services](../file-folder-services.md) and [locking](../locking.md) describe the current mutation boundaries.
