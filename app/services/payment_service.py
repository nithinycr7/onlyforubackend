from typing import Dict, Optional
import razorpay
from fastapi import HTTPException, status
from app.core.config import settings

class PaymentService:
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )

    def create_order(self, amount: float, receipt: str, currency: str = "INR") -> Dict:
        """
        Create a Razorpay order.
        Amount should be in rupees (will be converted to paise).
        """
        try:
            data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": currency,
                "receipt": receipt,
                "payment_capture": 1  # Auto capture
            }
            order = self.client.order.create(data=data)
            return order
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create payment order: {str(e)}"
            )

    def verify_payment(
        self, 
        razorpay_order_id: str, 
        razorpay_payment_id: str, 
        razorpay_signature: str
    ) -> bool:
        """
        Verify Razorpay payment signature.
        """
        try:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
        except Exception as e:
            print(f"Payment verification failed: {e}")
            return False

payment_service = PaymentService()
