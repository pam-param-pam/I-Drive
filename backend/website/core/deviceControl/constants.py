from typing import Literal

StatusType = Literal["idle", "pending_master", "pending_slave", "active_master", "active_slave"]

ErrorType = Literal[
    "masterRecentlyRejected",
    "slaveRecentlyRejected",
    "masterIsBusy",
    "slaveIsBusy",
    "pendingExists",
    "noPendingRequest",
    "noActivePair",
    "notActiveMaster",
    "badDeviceId"
]
