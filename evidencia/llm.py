"""Capa de proveedor del modelo.

Aislada tras un `Protocol` por dos razones prácticas: los tests corren sin red
ni credenciales, y el arnés de evaluación puede repetir una tanda exacta sin
volver a pagarla.
"""

from __future__ import annotations

from typing import Protocol

from evidencia.modelos import LoteCrudo
from evidencia.prompts import PLANTILLA_USUARIO, SISTEMA

MODELO_POR_DEFECTO = "claude-opus-5"


class ErrorProveedor(RuntimeError):
    """El proveedor no pudo devolver una extracción utilizable."""


class ProveedorLLM(Protocol):
    """Contrato mínimo: un fragmento de texto entra, un lote crudo sale."""

    nombre: str

    def extraer(self, fragmento: str) -> LoteCrudo: ...


class ProveedorAnthropic:
    """Extracción con la API de Claude y salida estructurada."""

    def __init__(
        self,
        modelo: str = MODELO_POR_DEFECTO,
        max_tokens: int = 16000,
        effort: str | None = None,
        cliente=None,
    ) -> None:
        self.modelo = modelo
        self.max_tokens = max_tokens
        self.effort = effort
        self.nombre = modelo
        self._cliente = cliente

    @property
    def cliente(self):
        # Import perezoso: el paquete `anthropic` no hace falta para los tests
        # ni para inspeccionar resultados ya cacheados.
        if self._cliente is None:
            import anthropic

            self._cliente = anthropic.Anthropic()
        return self._cliente

    def extraer(self, fragmento: str) -> LoteCrudo:
        parametros: dict = {
            "model": self.modelo,
            "max_tokens": self.max_tokens,
            "system": SISTEMA,
            "messages": [
                {"role": "user", "content": PLANTILLA_USUARIO.format(texto=fragmento)}
            ],
            "output_format": LoteCrudo,
            "thinking": {"type": "adaptive"},
        }
        # `effort` es opcional a propósito: omitirlo deja la llamada idéntica al
        # ejemplo documentado del SDK. Se pasa solo si alguien lo pide.
        if self.effort is not None:
            parametros["output_config"] = {"effort": self.effort}

        respuesta = self.cliente.messages.parse(**parametros)

        if respuesta.stop_reason == "refusal":
            detalle = getattr(respuesta, "stop_details", None)
            raise ErrorProveedor(f"El modelo rechazó la petición: {detalle}")
        if respuesta.stop_reason == "max_tokens":
            raise ErrorProveedor(
                "La respuesta se truncó por max_tokens; reduce el tamaño del fragmento."
            )

        lote = respuesta.parsed_output
        if lote is None:
            raise ErrorProveedor("La respuesta no contenía salida estructurada.")
        return lote


class ProveedorFalso:
    """Proveedor determinista para tests y para reproducir una tanda.

    Acepta un mapa fragmento -> lote, o un invocable.
    """

    def __init__(self, respuestas, nombre: str = "falso") -> None:
        self._respuestas = respuestas
        self.nombre = nombre
        self.llamadas: list[str] = []

    def extraer(self, fragmento: str) -> LoteCrudo:
        self.llamadas.append(fragmento)
        if callable(self._respuestas):
            return self._respuestas(fragmento)
        if fragmento in self._respuestas:
            return self._respuestas[fragmento]
        raise ErrorProveedor("ProveedorFalso no tiene respuesta para ese fragmento.")
