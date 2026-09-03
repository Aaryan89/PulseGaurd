import logging
from typing import Dict, Any, List
from datetime import datetime

# Configure local logging for the webhook stub
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebhookStub")

import os
import time

class WebhookConfig:
    enabled: bool = os.getenv("WEBHOOK_ENABLED", "true").lower() == "true"
    url: str = os.getenv("WEBHOOK_URL", "http://localhost:8000/internal/webhook-stub")

class WebhookManager:
    def __init__(self):
        self.config = WebhookConfig()
        self.recent_notifications: List[Dict[str, Any]] = []
        self.max_history = 50
        
        self.batch_queue: List[Dict[str, Any]] = []
        self.fires_this_sec = 0
        self.current_sec = 0
        self.max_fires_per_sec = 50
        
        self.summary_count = 0
        self.last_summary_time = time.time()

    def fire_webhook(self, payload: Dict[str, Any]):
        if not self.config.enabled:
            return
            
        now = time.time()
        current_sec = int(now)
        
        if current_sec > self.current_sec:
            self.current_sec = current_sec
            self.fires_this_sec = 0
            
        # Log a summary every 10 seconds if there was activity
        if now - self.last_summary_time > 10:
            if self.summary_count > 0:
                logger.info(f"Summary: {self.summary_count} webhooks processed in the last 10s.")
                self.summary_count = 0
            self.last_summary_time = now
            
        self.summary_count += 1
        
        if payload.get("tier") == "review":
            self.batch_queue.append(payload)
            # Add to UI history but don't log immediately to prevent log flood
            self._add_to_history(payload)
            
            if len(self.batch_queue) >= 100:
                self.flush_batch()
            return
            
        # For non-review (block), rate limit the actual firing
        if self.fires_this_sec < self.max_fires_per_sec:
            logger.debug(f"Firing webhook to {self.config.url} with payload: {payload}")
            self.fires_this_sec += 1
        
        self._add_to_history(payload)

    def _add_to_history(self, payload: Dict[str, Any]):
        notification = {
            **payload,
            "fired_at": datetime.now().isoformat()
        }
        self.recent_notifications.insert(0, notification)
        if len(self.recent_notifications) > self.max_history:
            self.recent_notifications.pop()
            
    def flush_batch(self):
        if not self.batch_queue:
            return
            
        batch_payload = {
            "batch": True,
            "count": len(self.batch_queue),
            "tier": "review",
            "merchant_id": self.batch_queue[-1].get("merchant_id")
        }
        if self.fires_this_sec < self.max_fires_per_sec:
            logger.debug(f"Firing batched webhook to {self.config.url} with payload: {batch_payload}")
            self.fires_this_sec += 1
            
        self.batch_queue.clear()

    def get_recent_notifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.recent_notifications[:limit]

# Global instance
webhook_manager = WebhookManager()
