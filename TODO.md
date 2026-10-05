# Current implementation gaps

These are observations from the current source, not a schedule or a list of completed migrations.

- Add retention/cleanup policy for completed deletion jobs and scopes. The implemented pipeline retains those records for inspection; see [delete.md](delete.md).
- Resolve the remaining deletion model overlap: `DeletionJob` groups scope progress and request context, but retains unused legacy fragment/failure fields; and both files and folders retain `ItemState` and `state_changed_at`. A separate file availability field has not been implemented.
- Decide whether deletion-scope conflicts require database enforcement. Current composite parent/owner constraints enforce ownership consistency, but there are no scope-conflict triggers or stored procedures. See [locking.md](locking.md).
- Review bounded subtree enumeration in `namespace_service.list_folder_subtree`: it collects descendant folder IDs before slicing to 1,000 folders and 1,000 files. This is neither pagination nor a complete subtree result.
- Review authorization and invalidation around response-level caching, including `get_folder_file_stats`'s one-minute `cache_page` decorator. Its function body authorizes before constructing a response, but a cached HTTP response can bypass that body.
- Decide issued signed-URL revocation semantics. ZIP records do not retain original share or lock versions; password/share changes alone cannot be documented as revoking those links.
- Expand authorization and concurrency regression coverage beyond the deletion integration tests in `backend/test_deletion_workflow.py`. Those tests exercise PostgreSQL locks/aggregates with mocked Discord and broker calls.
- Verify multi-process and multi-pod Prometheus behavior before scaling the backend.

Successful namespace operations are deleted, so request-ID deduplication lasts only while the row exists. WebSocket delivery is best effort. Stronger idempotency retention or event delivery would require explicit additional storage.
