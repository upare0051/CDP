"""Cube semantic-layer proxy routes.

The frontend hits these instead of Cube directly so we can centralize auth,
RLS, and the `Continue wait` poll. Implementation delegates to
`app.services.cube_client`.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.cube_client import (
    CubeQueryError,
    CubeUnavailableError,
    cube_load,
    cube_meta,
    cube_sql,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/cube", tags=["cube"])


class CubeLoadRequest(BaseModel):
    query: Dict[str, Any]


@router.get("/meta")
def get_cube_meta() -> Dict[str, Any]:
    try:
        return cube_meta()
    except CubeUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Cube unreachable: {e}")


@router.post("/load")
def post_cube_load(req: CubeLoadRequest) -> Dict[str, Any]:
    try:
        return cube_load(req.query)
    except CubeQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except CubeUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Cube unreachable: {e}")


@router.post("/sql")
def post_cube_sql(req: CubeLoadRequest) -> Dict[str, Any]:
    try:
        return cube_sql(req.query)
    except CubeQueryError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except CubeUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Cube unreachable: {e}")
