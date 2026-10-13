from django.db import connection, transaction


_SCOPE_LOCK_NAMESPACE = 1229210198  # Stable application advisory-lock namespace.


def _require_transaction() -> None:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Namespace barriers require transaction.atomic()")


def _require_postgresql() -> None:
    if connection.vendor != "postgresql":
        raise RuntimeError(f"Namespace barriers require PostgreSQL; active database vendor is '{connection.vendor}'")


def lock_owner_scope_shared(owner_id: int) -> None:
    """Hold a transaction-scoped owner lock that allows other ordinary mutations.

    Deletion admission takes the exclusive variant, so it cannot race these mutations.
    """
    _require_postgresql()
    _require_transaction()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock_shared(%s, %s)", [_SCOPE_LOCK_NAMESPACE, owner_id])


def lock_owner_scope_exclusive(owner_id: int) -> None:
    """Serialize deletion admission against other namespace mutations for this owner."""
    _require_postgresql()
    _require_transaction()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [_SCOPE_LOCK_NAMESPACE, owner_id])
