"""Modelos de dominio.

Separación deliberada entre lo que devuelve el modelo (`AfirmacionCruda`) y lo
que el sistema acepta (`Afirmacion`). Nada cruza esa frontera sin pasar por la
verificación de anclaje: es la regla que impide que el modelo invente
afirmaciones que no están en el texto.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TipoAfirmacion(str, Enum):
    """Taxonomía de enunciados.

    Solo `HECHO_VERIFICABLE` pasa a las fases de recuperación de evidencia. El
    resto se conserva en la salida para que el usuario vea qué se descartó y
    por qué — descartar en silencio es indistinguible de fallar.
    """

    HECHO_VERIFICABLE = "hecho_verificable"
    OPINION = "opinion"
    PREDICCION = "prediccion"
    JUICIO_VALOR = "juicio_valor"


class NivelAnclaje(str, Enum):
    """Cómo se logró anclar la cita al texto original.

    Es un diagnóstico de calidad del prompt, no un detalle interno: si muchas
    afirmaciones se anclan en nivel `RELAJADO`, el modelo está reescribiendo
    las citas en vez de copiarlas, y eso hay que arreglarlo en el prompt.
    """

    EXACTO = "exacto"
    NORMALIZADO = "normalizado"
    RELAJADO = "relajado"


class AfirmacionCruda(BaseModel):
    """Lo que devuelve el modelo. No es de fiar hasta verificarse."""

    texto: str = Field(
        description=(
            "La afirmación reescrita de forma autocontenida: sin pronombres ni "
            "referencias que dependan del resto del texto."
        )
    )
    cita: str = Field(
        description="Fragmento copiado literalmente del texto de entrada que contiene la afirmación."
    )
    tipo: TipoAfirmacion
    entidades: list[str] = Field(
        default_factory=list,
        description="Personas, organizaciones, lugares, fechas o magnitudes mencionadas.",
    )
    verificabilidad: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = imposible de verificar con fuentes públicas; 1 = trivialmente comprobable.",
    )


class LoteCrudo(BaseModel):
    """Envoltorio de la respuesta estructurada del modelo."""

    afirmaciones: list[AfirmacionCruda]


class Afirmacion(BaseModel):
    """Afirmación verificada: su cita existe literalmente en el texto de entrada."""

    id: str
    texto: str
    tipo: TipoAfirmacion
    entidades: list[str] = Field(default_factory=list)
    verificabilidad: float

    cita: str = Field(description="Substring exacto del texto de entrada, recuperado por offsets.")
    inicio: int
    fin: int
    nivel_anclaje: NivelAnclaje
    cita_ambigua: bool = Field(
        default=False,
        description="La cita aparece más de una vez en el texto; los offsets son de la primera.",
    )
    advertencias: list[str] = Field(default_factory=list)


class AfirmacionRechazada(BaseModel):
    """Afirmación que el modelo produjo y el sistema no aceptó."""

    texto: str
    cita_propuesta: str
    motivo: str


class ResultadoExtraccion(BaseModel):
    """Salida completa de la Fase 1, incluidos los rechazos."""

    afirmaciones: list[Afirmacion] = Field(default_factory=list)
    rechazadas: list[AfirmacionRechazada] = Field(default_factory=list)
    caracteres_entrada: int = 0
    fragmentos: int = 1
    desde_cache: bool = False

    @property
    def hechos(self) -> list[Afirmacion]:
        """Las únicas que avanzan a la Fase 2."""
        return [a for a in self.afirmaciones if a.tipo is TipoAfirmacion.HECHO_VERIFICABLE]

    @property
    def tasa_rechazo(self) -> float:
        total = len(self.afirmaciones) + len(self.rechazadas)
        return len(self.rechazadas) / total if total else 0.0
