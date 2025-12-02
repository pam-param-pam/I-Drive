from typing import List, Dict, Union, Optional, Any, TypedDict

from ..dataModels.http import RequestContext

EventData = Union[Dict[str, Any], str, None]

class InnerEvent(TypedDict, total=False):
    op_code: int
    data: List[Union[Dict[str, Any], str, None]]

class WebsocketEnvelope(TypedDict, total=False):
    is_encrypted: bool
    event: Union[InnerEvent, Dict[str, Any]]
    folder_context_id: Optional[str]
    lockFrom: Optional[str]

class RequestContextDict(TypedDict):
    user_id: str
    request_id: int
    device_id: Optional[str]

class WebsocketEvent(TypedDict):
    type: str
    context: RequestContextDict
    ws_payload: WebsocketEnvelope

class WebsocketLogoutEvent(TypedDict):
    type: str
    context: RequestContextDict
    token_hash: str
