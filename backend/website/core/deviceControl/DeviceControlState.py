import time
from typing import Optional, Dict, Literal

from django.core.cache import cache

from ..errors import DeviceControlBadStateError
from ...constants import DEVICE_CONTROL_PENDING_TTL, DEVICE_CONTROL_ACTIVE_TTL, DEVICE_CONTROL_REJECTED_TTL


class DeviceControlState:
    StatusType = Literal["idle", "pending_master", "pending_slave", "active_master", "active_slave"]

    @staticmethod
    def _pending_key_master(master_id: str) -> str:
        return f"device_control_pending:{master_id}"

    @staticmethod
    def _pending_key_slave(slave_id: str) -> str:
        return f"device_control_pending_reverse:{slave_id}"

    @staticmethod
    def _rejected_key_master(master_id: str) -> str:
        return f"device_control_rejected:{master_id}"

    @staticmethod
    def _rejected_key_slave(slave_id: str) -> str:
        return f"device_control_rejected_reverse:{slave_id}"

    @staticmethod
    def _active_key_master(master_id: str) -> str:
        return f"device_control:{master_id}"

    @staticmethod
    def _active_key_slave(slave_id: str) -> str:
        return f"device_control_reverse:{slave_id}"

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

    @classmethod
    def create_pending(cls, master_id: str, slave_id: str) -> None:
        # Rejected state check ----
        rejected_slave = cache.get(cls._rejected_key_master(master_id))
        if rejected_slave:
            raise DeviceControlBadStateError("master_recently_rejected")

        rejected_master = cache.get(cls._rejected_key_slave(slave_id))
        if rejected_master:
            raise DeviceControlBadStateError("slave_recently_rejected")

        # If one side was recently rejected, the other must be idle
        # In master → slave direction
        if rejected_slave:
            # master was rejected by someone -> slave must be idle
            if (cls.master_has_active(slave_id)
                    or cls.slave_has_active(slave_id)
                    or cls.master_has_pending(slave_id)
                    or cls.slave_has_pending(slave_id)):
                raise DeviceControlBadStateError("peer_not_idle_after_reject")

        if rejected_master:
            # slave was rejected by someone -> master must be idle
            if (cls.master_has_active(master_id)
                    or cls.slave_has_active(master_id)
                    or cls.master_has_pending(master_id)
                    or cls.slave_has_pending(master_id)):
                raise DeviceControlBadStateError("peer_not_idle_after_reject")

        # Check active conflicts
        if cls.master_has_active(master_id) or cls.slave_has_active(master_id):
            raise DeviceControlBadStateError("master_is_busy")

        if cls.master_has_active(slave_id) or cls.slave_has_active(slave_id):
            raise DeviceControlBadStateError("slave_is_busy")

        # Check existing pending
        if cls.master_has_pending(master_id):
            raise DeviceControlBadStateError("pending_exists")

        if cls.slave_has_pending(slave_id):
            raise DeviceControlBadStateError("slave_already_pending")

        # Create links
        cache.set(cls._pending_key_master(master_id), slave_id, timeout=DEVICE_CONTROL_PENDING_TTL)
        cache.set(cls._pending_key_slave(slave_id), master_id, timeout=DEVICE_CONTROL_PENDING_TTL)

    @classmethod
    def approve_pending(cls, master_id: str, slave_id: str) -> None:
        # Validate pending(master → slave)
        if cls.master_has_pending(master_id) != slave_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Validate pending(slave → master)
        if cls.slave_has_pending(slave_id) != master_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Promote to active (two-way)
        cache.set(cls._active_key_master(master_id), slave_id, timeout=DEVICE_CONTROL_ACTIVE_TTL)
        cache.set(cls._active_key_slave(slave_id), master_id, timeout=DEVICE_CONTROL_ACTIVE_TTL)

        # Clear pending (strict version will re-validate)
        cls.clear_pending(master_id, slave_id)

    @classmethod
    def clear_pending(cls, master_id: str, slave_id: str) -> None:
        # Check that pending(master) → slave matches
        if cls.master_has_pending(master_id) != slave_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Check that pending(slave) → master matches
        if cls.slave_has_pending(slave_id) != master_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Clear both sides
        cache.delete(cls._pending_key_master(master_id))
        cache.delete(cls._pending_key_slave(slave_id))

    @classmethod
    def reject_pending(cls, master_id: str, slave_id: str) -> None:
        # Validate pending(master → slave)
        if cls.master_has_pending(master_id) != slave_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Validate pending(slave → master)
        if cls.slave_has_pending(slave_id) != master_id:
            raise DeviceControlBadStateError("no_pending_request")

        # Clear pending using strict version
        cls.clear_pending(master_id, slave_id)

        # Set rejected states
        cache.set(cls._rejected_key_master(master_id), slave_id, timeout=DEVICE_CONTROL_REJECTED_TTL)
        cache.set(cls._rejected_key_slave(slave_id), master_id, timeout=DEVICE_CONTROL_REJECTED_TTL)

    @classmethod
    def clear_active(cls, master_id: str, slave_id: str) -> None:
        # Validate master → slave
        if cls.master_has_active(master_id) != slave_id:
            raise DeviceControlBadStateError("no_active_pair")

        # Validate slave → master
        if cls.slave_has_active(slave_id) != master_id:
            raise DeviceControlBadStateError("no_active_pair")

        # Clear both sides
        cache.delete(cls._active_key_master(master_id))
        cache.delete(cls._active_key_slave(slave_id))

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

    @staticmethod
    def _get_ttl_raw(key: str) -> Optional[int]:
        ttl = cache.ttl(key)
        return ttl if ttl >= 0 else None

    @classmethod
    def _get_expiry(cls, key: str) -> Optional[int]:
        ttl = cls._get_ttl_raw(key)
        if ttl is None:
            return None
        return int(time.time()) + ttl

    @classmethod
    def get_status(cls, device_id: str) -> Dict[str, Optional[StatusType]]:
        # 1) Active (master)
        slave = cls.master_has_active(device_id)
        if slave:
            expiry = cls._get_expiry(cls._active_key_master(device_id))
            return {"status": "active_master", "peer": slave, "expiry": expiry}

        # 2) Active (slave)
        master = cls.slave_has_active(device_id)
        if master:
            expiry = cls._get_expiry(cls._active_key_slave(device_id))
            return {"status": "active_slave", "peer": master, "expiry": expiry}

        # 3) Pending (master initiated)
        pending_slave = cls.master_has_pending(device_id)
        if pending_slave:
            expiry = cls._get_expiry(cls._pending_key_master(device_id))
            return {"status": "pending_master", "peer": pending_slave, "expiry": expiry}

        # 4) Pending (slave awaiting approval)
        pending_master = cls.slave_has_pending(device_id)
        if pending_master:
            expiry = cls._get_expiry(cls._pending_key_slave(device_id))
            return {"status": "pending_slave", "peer": pending_master, "expiry": expiry}

        # 5) Recently rejected (master)
        rejected_slave = cache.get(cls._rejected_key_master(device_id))
        if rejected_slave:
            expiry = cls._get_expiry(cls._rejected_key_master(device_id))
            return {"status": "rejected_master", "peer": rejected_slave, "expiry": expiry}

        # 6) Nothing
        return {"status": "idle", "peer": None, "expiry": None}
