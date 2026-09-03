import os
import razorpay
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

def get_client() -> Optional[razorpay.Client]:
    """
    Returns an authenticated Razorpay client if credentials exist, otherwise None.
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_test_order(amount_paise: int, currency: str = "INR", receipt: str = "receipt_test") -> Optional[Dict[str, Any]]:
    """
    Creates a Razorpay test mode order for the given amount in paise.
    """
    client = get_client()
    if not client:
        return None
        
    data = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt,
        "notes": {
            "demo_type": "pulseguard_live_test"
        }
    }
    try:
        return client.order.create(data=data)
    except Exception as e:
        print(f"Razorpay API Error (Create Order): {e}")
        return None

def fetch_payment(payment_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the full details of a Razorpay payment by its ID.
    """
    client = get_client()
    if not client:
        return None
        
    try:
        return client.payment.fetch(payment_id)
    except Exception as e:
        print(f"Razorpay API Error (Fetch Payment): {e}")
        return None
