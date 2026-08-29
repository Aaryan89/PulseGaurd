import logging
from typing import Dict, Any, List
from datetime import datetime

# Configure local logging for the webhook stub
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebhookStub")

class WebhookConfig:
    enabled: bool = True
    url: str = "http://localhost:8000/internal/webhook-stub" # Configurable URL

class WebhookManager:
    def __init__(self):
        self.config = WebhookConfig()
        self.recent_notifications: List[Dict[str, Any]] = []
        self.max_history = 50

    def fire_webhook(self, payload: Dict[str, Any]):
        if not self.config.enabled:
            return
            
        # Simulate a POST request by just logging and storing it locally
        logger.info(f"Firing webhook to {self.config.url} with payload: {payload}")
        
        # Add a firing timestamp
        notification = {
            **payload,
            "fired_at": datetime.now().isoformat()
        }
        
        self.recent_notifications.insert(0, notification)
        if len(self.recent_notifications) > self.max_history:
            self.recent_notifications.pop()

    def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.recent_notifications[:limit]

# Global instance
webhook_manager = WebhookManager()
