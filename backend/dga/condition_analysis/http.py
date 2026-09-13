"""Authenticated read transport for the analysis application interface."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .public import TrendQuery, TransformerTrends


def http_router(trends: TransformerTrends, actor_dependency):
    router = APIRouter(prefix='/api/condition-analysis')

    @router.get('/transformers/{asset_id}/trends')
    def trend(asset_id: UUID, filters: Annotated[TrendQuery, Query()], response: Response,
              actor=Depends(actor_dependency)):
        response.headers['Cache-Control'] = 'no-store'
        try:
            return trends.query(actor, asset_id, filters)
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={'code': 'trend_source_unavailable'},
                                headers={'Cache-Control': 'no-store'})

    return router
