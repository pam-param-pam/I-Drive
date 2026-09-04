from prometheus_client import Counter, REGISTRY
from prometheus_client.registry import DuplicateTimeseries


def _counter(name: str, documentation: str, labels: tuple[str, ...] = ()) -> Counter:
    registry_name = name.removesuffix("_total")
    existing = REGISTRY._names_to_collectors.get(registry_name)
    if existing is not None:
        return existing

    try:
        return Counter(name, documentation, labelnames=labels)
    except DuplicateTimeseries:
        return REGISTRY._names_to_collectors[registry_name]


STREAMED_BYTES = _counter(
    "idrive_streamed_bytes_total",
    "Number of bytes returned by media stream views.",
)

def record_stream_response(response) -> None:
    """Count response bytes without consuming streaming responses early."""
    if not response.streaming:
        STREAMED_BYTES.inc(len(response.content))
        return

    content = response.streaming_content

    if response.is_async:
        async def counted_content():
            async for chunk in content:
                STREAMED_BYTES.inc(len(chunk))
                yield chunk
    else:
        def counted_content():
            for chunk in content:
                STREAMED_BYTES.inc(len(chunk))
                yield chunk

    response.streaming_content = counted_content()
