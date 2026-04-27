
def get_thumbnail_key(file_id: str) -> str:
    return f"thumbnail:{file_id}"

def get_folder_content_key(folder_id: str) -> str:
    return f"folder-content:{folder_id}"

def get_folder_usage_key(folder_id: str) -> str:
    return f"folder-usage:{folder_id}"

def get_qr_session_key(session_id: str) -> str:
    return f"qr-session:{session_id}"

def get_qr_ip_key(qr_ip: str) -> str:
    return f"qr-ip:{qr_ip}"

def get_discord_message_key(message_id: str) -> str:
    return f"discord-message:{message_id}"

def get_total_used_size_key(user_id: int) -> str:
    return f"total-used-size:{user_id}"

