"""Evaluation access boundary.

Evaluation profiles, runs, scoring, and traces belong to later tickets.
"""

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin


router = APIRouter()


@router.get("/admin/access")
async def verify_management_access(_user: dict = Depends(require_admin)) -> dict:
    """Verify that the caller may use future Evaluation management operations."""
    return {
        "success": True,
        "data": {"can_manage": True},
        "message": "管理员权限验证成功",
    }
