def build_thread_id(user_id: int, client_thread_id: str) -> str:
    return f"{user_id}_{client_thread_id}"
