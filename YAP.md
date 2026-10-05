# How iDrive works

iDrive stores file bytes as Discord attachments and keeps their metadata in PostgreSQL. The browser upload pipeline prepares fragments, encryption, checksums, thumbnails and media metadata, uploads attachments through webhooks, then submits the resulting metadata to Django.

## Components

| Component | Current responsibility |
| --- | --- |
| Vue 3 / Vite frontend | Browsing, uploads, downloads, previews, Pinia state and translated WebSocket toasts. |
| Django / DRF / Daphne / Channels backend | Authentication, resource authorization, metadata mutations, signed downloads and streaming. |
| PostgreSQL | Metadata, adjacency-list hierarchy, lifecycle markers, aggregates and durable work. |
| Redis | Caches, Celery broker, Channels layer and shared Discord credential/rate-limit state. |
| Celery and Beat | Move/trash/restore batches, folder hash/height repairs, raw-image thumbnails and scheduled cleanup. |
| NGINX | Production frontend serving and backend proxying. |
| Prometheus / Grafana | Metrics and provisioned monitoring dashboards. |

The backend streams fragments from Discord, supports range requests and server decryption, and builds streaming ZIP downloads. The frontend also supports client decryption. Upload sizes and Discord request limits are configuration/runtime concerns; this document does not assume a fixed platform limit or request rate.

Webhooks upload attachments without exposing bot tokens to the browser. Backend bot credentials support Discord API operations. The Discord integration tracks credential availability and rate limits; adding credentials does not eliminate channel or global limits.

## Namespace state

Celery uses `RecursiveTaskDiscovery` to lazily import `tasks.py` or every Python
module beneath an installed Django app's `tasks/` directory, including nested
directories. New task modules do not need a manual Celery `include` entry.

`Folder.parent_id` is the hierarchy. Explicit trash uses `trashed_at` on files/folders. Folder locks use `FolderLockScope`; deletion uses active `DeletionScope` records alongside the existing resource lifecycle fields. Authorization resolves current ancestry and inherited state.

Move, trash and restore requests persist a `NamespaceOperation` and return HTTP 202. Workers commit bounded batches and cursor advancement together. Permanent deletion establishes a logical scope barrier, processes bounded child/attachment pages, finalizes empty folders, and recovers through a 15-second supervisor.

## Implementation references

- [Resource authorization](authorization-access-api.md)
- [File and folder services](file-folder-services.md)
- [Folder hierarchy, hashes and root policies](folder-operations.md)
- [Locking](locking.md)
- [Stored aggregates](stored-resource-aggregates.md)
- [Projected reads](read-permission-fast-path.md)
- [Namespace Celery operations](namespace-celery-operations.md)
- [Permanent deletion status](delete.md)

See [README.md](README.md) for setup and [TODO.md](TODO.md) for current gaps.
