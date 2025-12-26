from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any
from uuid import UUID

from app.db.session import get_db
from app.db.models import Booking, BookingStatus, User
from app.api.deps import get_current_user
from app.schemas import PaymentOrderCreate, PaymentOrderResponse, PaymentVerify, BookingResponse
from app.services.payment_service import payment_service
from app.core.config import settings

router = APIRouter()

@router.post("/create-order", response_model=PaymentOrderResponse)
async def create_payment_order(
    payment_data: PaymentOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Razorpay order for a booking.
    """
    # 1. Fetch booking
    result = await db.execute(
        select(Booking).where(Booking.id == payment_data.booking_id)
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
        
    # 2. Verify ownership
    if booking.fan_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to pay for this booking"
        )
        
    # 3. Create Razorpay order
    # Ensure amount is valid
    if not booking.amount_paid or booking.amount_paid <= 0:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking amount"
        )
        
    try:
        order = payment_service.create_order(
            amount=float(booking.amount_paid),
            receipt=str(booking.id)
        )
    except Exception as e:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        
    # 4. Update booking with order_id
    booking.razorpay_order_id = order['id']
    booking.payment_status = 'PENDING'
    await db.commit()
    await db.refresh(booking)
    
    return {
        "order_id": order['id'],
        "currency": order['currency'],
        "amount": order['amount'],
        "key_id": settings.razorpay_key_id,
        "booking_id": booking.id
    }

@router.post("/verify", response_model=BookingResponse)
async def verify_payment(
    verification_data: PaymentVerify,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a Razorpay payment and update booking status.
    """
    # 1. Verify signature
    is_valid = payment_service.verify_payment(
        razorpay_order_id=verification_data.razorpay_order_id,
        razorpay_payment_id=verification_data.razorpay_payment_id,
        razorpay_signature=verification_data.razorpay_signature
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature"
        )
        
    # 2. Fetch booking by order_id
    result = await db.execute(
        select(Booking).where(Booking.razorpay_order_id == verification_data.razorpay_order_id)
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found for this order"
        )
        
    # 3. Update status
    booking.payment_status = 'PAID'
    # Important: Do NOT move to PENDING_QUESTION here if user still needs to submit question.
    # If they already submitted question (e.g. text), then maybe? 
    # For now, let's assume they haven't submitted question yet, or if they have, keep as is.
    # Usually flow is: Book -> Pay -> Submit Question OR Book & Submit -> Pay.
    # Let's assume Book (PENDING_PAYMENT?) -> Pay -> Submit Question (PENDING_QUESTION).
    # But current status is PENDING_QUESTION by default.
    # If we enforce payment first, initial status should be 'payment_pending'.
    
    # For this MVP, let's say status allows submitting question only if payment is PAID.
    # We'll stick to 'payment_status' column for checking payment.
    
    booking.razorpay_payment_id = verification_data.razorpay_payment_id
    booking.razorpay_signature = verification_data.razorpay_signature
    
    await db.commit()
    await db.refresh(booking)
    
    return booking
