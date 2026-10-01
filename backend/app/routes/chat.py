from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from ..models import ChatRequest
from ..security import authorize

router = APIRouter()


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    await authorize(request, "chat")
    service = request.app.state.callmissed
    if body.stream:
        response = await service.open_stream(body)
        return StreamingResponse(
            service.stream(response),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
    return await service.chat(body)
