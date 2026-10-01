from fastapi import APIRouter, Request
from ..models import ImageRequest
from ..security import authorize

router = APIRouter()


@router.post("/images")
async def images(body: ImageRequest, request: Request):
    await authorize(request, "images")
    return await request.app.state.callmissed.image(body)
