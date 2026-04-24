from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...io import StoreError
from ...sync import SyncError, execute_sync, plan_sync
from ...store.projects import StoreCtx
from ..deps import get_ctx

router = APIRouter(tags=["sync"])


class SyncPlanBody(BaseModel):
    operation: str
    entity_type: str
    entity_id: str
    include_links: bool = False
    include_descendants: bool = False
    cloud_api_base: str | None = None
    bearer_token: str | None = None


class SyncExecuteBody(SyncPlanBody):
    pass


def _raise_store_error(e: StoreError):
    status = {"NOT_FOUND": 404, "CONFLICT": 409}.get(e.code, 400)
    raise HTTPException(status_code=status, detail=str(e))


@router.post("/sync/plan")
def get_sync_plan(body: SyncPlanBody, ctx: StoreCtx = Depends(get_ctx)):
    try:
        plan = plan_sync(
            ctx,
            operation=body.operation,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            include_links=body.include_links,
            include_descendants=body.include_descendants,
            cloud_api_base=body.cloud_api_base,
            bearer_token=body.bearer_token,
        )
        return plan.to_dict()
    except StoreError as e:
        _raise_store_error(e)
    except SyncError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync/execute")
def execute_sync_route(body: SyncExecuteBody, ctx: StoreCtx = Depends(get_ctx)):
    try:
        return execute_sync(
            ctx,
            operation=body.operation,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            include_links=body.include_links,
            include_descendants=body.include_descendants,
            cloud_api_base=body.cloud_api_base,
            bearer_token=body.bearer_token,
        )
    except StoreError as e:
        _raise_store_error(e)
    except SyncError as e:
        raise HTTPException(status_code=400, detail=str(e))
