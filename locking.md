# Current locking model

## Owner barrier

[namespace_lock_service](backend/website/services/namespace_lock_service.py) requires PostgreSQL and an active `transaction.atomic()`. It uses namespace key `1229210198` plus the owner ID with `pg_advisory_xact_lock_shared` or `pg_advisory_xact_lock`.

Ordinary namespace mutations acquire the shared barrier. File/folder deletion requests, deletion processing, attachment removal and user-root creation acquire the exclusive barrier. These are transaction-scoped locks, released on commit/rollback. Remote attachment removal holds the transaction open through Discord HTTP and acknowledgement.

The acquisition functions are blocking. They do not themselves set a lock timeout or implement nonblocking retry. Timeout behavior depends on database/session configuration.

## Hierarchy and file locks

`lock_folder_chains` first loads ancestor snapshots, then locks owner-scoped folders with `select_for_update()` ordered by ID. It rejects missing rows or changes in parent/height-bound state since the snapshot.

File commands use `lock_files_with_parents` to discover source parents, lock the affected folder chains, then lock files in ID order and verify their current parent/owner. Ordinary file mutations therefore lock folders before files; do not assume a preloaded model is still valid.

Folder move validates cycles and depth from parent chains and `subtree_height_bound`. `assert_no_active_scope_in_subtree` walks active folder-scope roots upward to reject overlapping folder operations. The resource loader also resolves direct file scopes and inherited folder scopes for permission checks.

## Work locks

A namespace worker acquires the owner shared barrier, then locks its `NamespaceOperation` with `select_for_update(skip_locked=True)`, then obtains resource locks. The operation row remains locked through mutation and cursor advancement. A duplicate task that cannot lock it returns.

Hash/height repairs take the shared owner barrier, lock the folder, then lock its work row. They use short database transactions and persistent work rows. There is no lease/claim-token protocol for these repairs or namespace batches.

Deletion uses a persisted claim token/heartbeat on each scope. Claim admission and mutations take the exclusive owner barrier followed by the scope row lock. A recent claim prevents duplicate execution; the supervisor republishes abandoned claims after five minutes. Every mutation verifies the token, and file/folder work items are not separately leased.

Message keep-set calculation, HTTP removal and local acknowledgement share a database transaction holding the owner barrier and scope row lock. The ordinary attachment-removal helper also takes the owner barrier. A replacement claim waits for remote acknowledgement and its heartbeat update. No session advisory locks or dedicated connections are used. The tradeoff is that other namespace mutations for the same owner wait during a remote request.

## Enforcement boundary

Composite parent/owner foreign keys enforce that a file or folder and its parent share an owner. Other model constraints enforce local invariants. They do not enforce ancestor deletion-scope conflicts, arbitrary cycles or maximum hierarchy depth.

There are no deletion-scope conflict triggers, deletion-only stored procedures or general prohibition on direct ORM writes in the current migrations. Scope checks are implemented at service/authorization boundaries. This limitation must remain explicit when reviewing admin, maintenance and future mutation paths.

See [delete.md](delete.md) for deletion status and [namespace-celery-operations.md](namespace-celery-operations.md) for batch recovery.
