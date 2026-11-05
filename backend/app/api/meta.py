from __future__ import annotations

from fastapi import APIRouter

from .. import config

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/taxonomy")
def taxonomy():
    """Business taxonomy from data/local.json, with generic defaults."""
    return config.taxonomy_config()
