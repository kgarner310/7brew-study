"""Aggregate v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import authorities, concepts, jurisdictions, propositions, research, search

api_router = APIRouter(prefix="/v1")
api_router.include_router(jurisdictions.router)
api_router.include_router(concepts.router)
api_router.include_router(authorities.router)
api_router.include_router(propositions.router)
api_router.include_router(search.router)
api_router.include_router(research.router)
