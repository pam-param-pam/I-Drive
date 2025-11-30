from typing import Optional, Dict, Literal, Union

from django.core.cache import cache

PENDING_TTL = 300
ACTIVE_TTL = 7200

StatusType = Literal[
    "idle",
    "pending_master",
    "pending_slave",
    "active_master",
    "active_slave",
]


class DeviceControlState:
    """Manages pending and active master/slave device control states using Redis."""

    # ------------------------------
    # Key helpers
    # ------------------------------
    @staticmethod
    def _pending_key_master(master_id: str) -> str:
        return f"device_control_pending:{master_id}"

    @staticmethod
    def _pending_key_slave(slave_id: str) -> str:
        return f"device_control_pending_reverse:{slave_id}"

    @staticmethod
    def _pending_meta_key(master_id: str) -> str:
        return f"device_control_pending_meta:{master_id}"

    @staticmethod
    def _active_key_master(master_id: str) -> str:
        return f"device_control:{master_id}"

    @staticmethod
    def _active_key_slave(slave_id: str) -> str:
        return f"device_control_reverse:{slave_id}"

    # ------------------------------
    # Lookup helpers
    # ------------------------------
    @classmethod
    def master_has_active(cls, master_id: str) -> Optional[str]:
        return cache.get(cls._active_key_master(master_id))

    @classmethod
    def slave_has_active(cls, slave_id: str) -> Optional[str]:
        return cache.get(cls._active_key_slave(slave_id))

    @classmethod
    def master_has_pending(cls, master_id: str) -> Optional[str]:
        return cache.get(cls._pending_key_master(master_id))

    @classmethod
    def slave_has_pending(cls, slave_id: str) -> Optional[str]:
        return cache.get(cls._pending_key_slave(slave_id))

    # ------------------------------
    # Pending creation
    # ------------------------------
    @classmethod
    def create_pending(cls, master_id: str, slave_id: str, meta: Optional[Dict] = None) -> bool:
        """
        Creates a pending master→slave control request.
        Raises ValueError if impossible.
        """
        # Check active conflicts
        if cls.master_has_active(master_id) or cls.slave_has_active(master_id):
            raise ValueError("master_is_busy")

        if cls.master_has_active(slave_id) or cls.slave_has_active(slave_id):
            raise ValueError("slave_is_busy")

        # Check existing pending
        if cls.master_has_pending(master_id):
            raise ValueError("pending_exists")

        if cls.slave_has_pending(slave_id):
            raise ValueError("slave_already_pending")

        # Create links
        cache.set(cls._pending_key_master(master_id), slave_id, timeout=PENDING_TTL)
        cache.set(cls._pending_key_slave(slave_id), master_id, timeout=PENDING_TTL)

        if meta is not None:
            cache.set(cls._pending_meta_key(master_id), meta, timeout=PENDING_TTL)

        return True

    # ------------------------------
    # Pending approval
    # ------------------------------
    @classmethod
    def approve_pending(cls, master_id: Optional[str] = None, slave_id: Optional[str] = None) -> bool:
        """
        Approves a pending control request and promotes it to active.
        Either master_id, slave_id, or both may be supplied.

        Raises:
            ValueError if no pending pair exists or IDs don't match.
        """

        # Resolve missing side
        if master_id and not slave_id:
            slave_id = cls.master_has_pending(master_id)
        elif slave_id and not master_id:
            master_id = cls.slave_has_pending(slave_id)

        # Ensure full pair resolved
        if not master_id or not slave_id:
            raise ValueError("no_pending_request")

        # Validate that the pending pair matches
        pending_slave = cls.master_has_pending(master_id)
        if pending_slave != slave_id:
            raise ValueError("no_pending_request")

        # Promote to active (two-way)
        cache.set(cls._active_key_master(master_id), slave_id, timeout=ACTIVE_TTL)
        cache.set(cls._active_key_slave(slave_id), master_id, timeout=ACTIVE_TTL)

        # Clear pending state
        cls.clear_pending(master_id, slave_id)

        return True

    # ------------------------------
    # Clearing pending
    # ------------------------------
    @classmethod
    def clear_pending(cls, master_id: Optional[str] = None, slave_id: Optional[str] = None) -> None:
        """
        Clears a pending master<->slave relationship.
        Either master_id, slave_id, or both may be provided.
        """

        # Resolve missing side
        if master_id and not slave_id:
            slave_id = cls.master_has_pending(master_id)
        elif slave_id and not master_id:
            master_id = cls.slave_has_pending(slave_id)

        # Nothing to clear
        if not master_id or not slave_id:
            return

        # Delete both sides
        cache.delete(cls._pending_key_master(master_id))
        cache.delete(cls._pending_key_slave(slave_id))
        cache.delete(cls._pending_meta_key(master_id))

    # ------------------------------
    # Clearing active
    # ------------------------------
    @classmethod
    def clear_active(cls, master_id: Optional[str] = None, slave_id: Optional[str] = None) -> None:
        if master_id and not slave_id:
            slave_id = cls.master_has_active(master_id)

        elif slave_id and not master_id:
            master_id = cls.slave_has_active(slave_id)

        if master_id:
            cache.delete(cls._active_key_master(master_id))
        if slave_id:
            cache.delete(cls._active_key_slave(slave_id))

    # ------------------------------
    # Get active pairs
    # ------------------------------
    @classmethod
    def get_active_slave_for_master(cls, master_id: str) -> Optional[str]:
        slave = cls.master_has_active(master_id)
        if not slave:
            return None
        return slave

    @classmethod
    def get_active_master_for_slave(cls, slave_id: str) -> Optional[str]:
        master = cls.slave_has_active(slave_id)
        if not master:
            return None
        return master

    # ------------------------------
    # NEW: get_status()
    # ------------------------------
    @classmethod
    def get_status(cls, device_id: str) -> Dict[str, Optional[Union[str, StatusType]]]:
        """
        Returns the status of the device:

        {
            "status": "idle" | "pending_master" | "pending_slave" | "active_master" | "active_slave",
            "peer": "<other-device-id>" | None
        }
        """

        # 1) Active (master)
        slave = cls.master_has_active(device_id)
        if slave:
            return {"status": "active_master", "peer": slave}

        # 2) Active (slave)
        master = cls.slave_has_active(device_id)
        if master:
            return {"status": "active_slave", "peer": master}

        # 3) Pending (master initiated)
        pending_slave = cls.master_has_pending(device_id)
        if pending_slave:
            return {"status": "pending_master", "peer": pending_slave}

        # 4) Pending (slave awaiting approval)
        pending_master = cls.slave_has_pending(device_id)
        if pending_master:
            return {"status": "pending_slave", "peer": pending_master}

        # 5) Nothing
        return {"status": "idle", "peer": None}
