"""Logs em JSON e métricas Prometheus.

Privacidade (LGPD): o log de requisição tem UMA linha por requisição e traz só o necessário
para operar: método, ROTA (o modelo, como `/relatos/{id}`, nunca o caminho com ids), status,
duração e um id de requisição aleatório. Ele NÃO traz: corpo, foto, descrição, parâmetros de
consulta (podem conter coordenadas exatas), cabeçalhos (X-Autor-Id, tokens) nem IP.

Métricas: o rótulo `rota` também é o modelo da rota; rotas inexistentes viram "desconhecida"
para a cardinalidade não explodir.
"""

import json
import logging
import sys
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOG_REQUISICAO = logging.getLogger("passo_seguro.requisicao")

# Campos extras que podem aparecer no JSON do log (lista fechada, de propósito).
_CAMPOS_PERMITIDOS = ("metodo", "rota", "status", "duracao_ms", "request_id", "tipo_erro", "local_erro", "evento")

# Rotas que não geram linha de log (verificação de vida, raspagem de métricas).
_SEM_LOG = {"/saude", "/metrics"}


class FormatadorJson(logging.Formatter):
    """Uma linha JSON por registro, só com campos permitidos."""

    def format(self, record: logging.LogRecord) -> str:
        linha: dict = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for campo in _CAMPOS_PERMITIDOS:
            valor = getattr(record, campo, None)
            if valor is not None:
                linha[campo] = valor
        if record.exc_info and record.exc_info[0] is not None:
            # Só o tipo e o local: a mensagem da exceção pode conter dados (ex.: linha do banco).
            linha["tipo_erro"] = record.exc_info[0].__name__
            quadros = traceback.extract_tb(record.exc_info[2])
            if quadros:
                ultimo = quadros[-1]
                linha["local_erro"] = f"{PurePath(ultimo.filename).name}:{ultimo.lineno}"
        return json.dumps(linha, ensure_ascii=False)


def configurar_logs(nivel: str = "INFO") -> None:
    """Põe todos os logs em JSON na saída padrão e desliga o access log do uvicorn."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FormatadorJson())
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(nivel.upper())
    for nome in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(nome)
        logger.handlers[:] = []
        logger.propagate = True
    # httpx/httpcore registram a URL completa de cada chamada que a API faz a outros serviços.
    for nome in ("httpx", "httpcore"):
        logging.getLogger(nome).setLevel(logging.WARNING)
    acesso = logging.getLogger("uvicorn.access")  # tem a query string no caminho
    acesso.handlers[:] = []
    acesso.propagate = False
    acesso.disabled = True


class Metricas:
    """Métricas HTTP em um registro próprio (uma instância por aplicação)."""

    def __init__(self) -> None:
        self.registro = CollectorRegistry()
        self.latencia = Histogram(
            "passo_seguro_http_request_duration_seconds",
            "Latência das requisições HTTP, por método e rota (modelo da rota).",
            ["metodo", "rota"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registro,
        )
        self.requisicoes = Counter(
            "passo_seguro_http_requests_total",
            "Total de requisições HTTP, por método, rota e status.",
            ["metodo", "rota", "status"],
            registry=self.registro,
        )
        self.em_andamento = Gauge(
            "passo_seguro_http_requests_in_progress",
            "Requisições em andamento agora (saturação).",
            registry=self.registro,
        )


def rota_do_escopo(scope: Scope) -> str:
    """Modelo da rota (`/relatos/{id}`), nunca o caminho real."""
    rota = scope.get("route")
    caminho = getattr(rota, "path", None)
    if caminho:
        return caminho
    if scope.get("path", "").startswith("/fotos/"):
        return "/fotos/{caminho}"
    return "desconhecida"


class ObservabilidadeMiddleware:
    """Mede e registra cada requisição HTTP (ASGI puro, sem ler o corpo)."""

    def __init__(self, app: ASGIApp, metricas: Metricas) -> None:
        self.app = app
        self.metricas = metricas

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        status = 500
        inicio = time.perf_counter()
        self.metricas.em_andamento.inc()

        async def send_com_id(mensagem: Message) -> None:
            nonlocal status
            if mensagem["type"] == "http.response.start":
                status = mensagem["status"]
                MutableHeaders(scope=mensagem)["X-Request-ID"] = request_id
            await send(mensagem)

        try:
            await self.app(scope, receive, send_com_id)
        finally:
            duracao = time.perf_counter() - inicio
            rota = rota_do_escopo(scope)
            metodo = scope["method"]
            self.metricas.em_andamento.dec()
            self.metricas.latencia.labels(metodo, rota).observe(duracao)
            self.metricas.requisicoes.labels(metodo, rota, str(status)).inc()
            if scope.get("path") not in _SEM_LOG:
                LOG_REQUISICAO.info(
                    "requisicao",
                    extra={
                        "metodo": metodo,
                        "rota": rota,
                        "status": status,
                        "duracao_ms": round(duracao * 1000, 1),
                        "request_id": request_id,
                    },
                )
