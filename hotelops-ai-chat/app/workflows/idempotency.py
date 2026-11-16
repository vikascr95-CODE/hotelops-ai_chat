import hashlib

def message_key(conversation_id: str, message: str, client_key: str | None = None) -> str:
    """Stable key for a retry; client keys take precedence when supplied."""
    raw = client_key or f"{conversation_id}:{message.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
