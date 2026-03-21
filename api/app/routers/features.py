"""Feature endpoints: list available features and get form schemas."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.client import Client
from app.services.auth_service import get_current_user
from app.services.feature_gate import get_user_visible_feature_ids, get_user_features_public
from app.core.feature_registry import get_feature

router = APIRouter(prefix="/api/v1/features", tags=["features"])


@router.get("")
async def list_features(user: User = Depends(get_current_user)):
    """Return all features visible to the current user (plan × role filtered)."""
    features = get_user_features_public(user)
    return {"features": features}


@router.get("/{feature_id}/schema")
async def get_feature_schema(
    feature_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return form schema for a specific feature, including dynamic select options.
    Dynamic fields like select_client and select_staff get populated with real data.
    """
    allowed = get_user_visible_feature_ids(user)
    if feature_id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Feature not available")

    feature = get_feature(feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature not found")

    schema = feature.to_public_dict()

    # Populate dynamic select options
    for field in schema["form_schema"]["fields"]:
        if field["type"] == "select_client":
            stmt = select(Client).where(Client.tenant_id == user.tenant_id)
            result = await db.execute(stmt)
            clients = result.scalars().all()
            field["options"] = [
                {"value": str(c.id), "label": f"{c.code_name} ({c.display_alias})"}
                for c in clients
            ]
        elif field["type"] == "select_staff":
            from app.models.user import User as UserModel, UserRole
            stmt = select(UserModel).where(
                UserModel.tenant_id == user.tenant_id,
                UserModel.role.in_([UserRole.TEACHER, UserRole.BCBA]),
            )
            result = await db.execute(stmt)
            staff = result.scalars().all()
            field["options"] = [
                {"value": str(s.id), "label": s.name}
                for s in staff
            ]

    return schema
