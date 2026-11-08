"""GET /metrics: métricas no formato Prometheus, protegidas por METRICS_TOKEN (não é do contrato)."""

from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.seguranca import exigir_token_metricas

router = APIRouter(include_in_schema=False)


@router.get("/metrics", dependencies=[Depends(exigir_token_metricas)])
def metricas(request: Request) -> Response:
    return Response(generate_latest(request.app.state.metricas.registro), media_type=CONTENT_TYPE_LATEST)
