import asyncio
import logging
from typing import Dict, List

logger = logging.getLogger("VisionAPI.session")

class SessionLogger:
    def __init__(self):
        self.sessions: Dict[str, List[str]] = {}

    def start_session(self, session_id: str):
        self.sessions[session_id] = []

    def log(self, session_id: str, message: str):
        if session_id in self.sessions:
            self.sessions[session_id].append(message)
            logger.info(f"[SESSION {session_id}] {message}")

    def get_logs(self, session_id: str) -> List[str]:
        return self.sessions.get(session_id, [])

    def end_session(self, session_id: str):
        # We might want to keep logs for a bit for polling to finish
        async def delayed_cleanup():
            await asyncio.sleep(60)
            if session_id in self.sessions:
                del self.sessions[session_id]
        asyncio.create_task(delayed_cleanup())

session_logger = SessionLogger()
