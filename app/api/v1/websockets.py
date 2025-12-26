from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from app.core.websockets import manager
from app.core.security import decode_token
from app.db.session import get_db
from app.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()

async def get_current_user_ws(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user

@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    # Authenticate
    payload = decode_token(token)
    user_id = None
    
    if payload:
        user_id = payload.get("sub")
    
    if not user_id:
        # Close with policy violation if invalid
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep connection alive and listen for any incoming (e.g. typing indicators)
            data = await websocket.receive_text()
            # For now we just echo or ignore, main logic is push from server
            # We could implement "typing" events here
            import json
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
