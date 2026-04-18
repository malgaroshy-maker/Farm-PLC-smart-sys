"""Farm endpoints — GET /api/v1/farm."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.farm import Farm
from app.schemas.farm import FarmResponse

router = APIRouter(prefix="/farm", tags=["Farm"])


@router.get("", response_model=FarmResponse)
async def get_farm(db: AsyncSession = Depends(get_db)):
    """Returns the farm metadata."""
    result = await db.execute(select(Farm))
    farm = result.scalar_one_or_none()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found. Run seed script first.")
    return farm
