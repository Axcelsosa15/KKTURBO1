"""Sistema de trazabilidad de evidencia — Fase 1: extracción de afirmaciones.

No decide si algo es verdadero. Extrae las afirmaciones verificables de un
texto y las ancla a su cita literal, para que las fases siguientes puedan
buscar evidencia sobre cada una por separado.
"""

from evidencia.modelos import (
    Afirmacion,
    AfirmacionCruda,
    NivelAnclaje,
    ResultadoExtraccion,
    TipoAfirmacion,
)

__all__ = [
    "Afirmacion",
    "AfirmacionCruda",
    "NivelAnclaje",
    "ResultadoExtraccion",
    "TipoAfirmacion",
]
__version__ = "0.1.0"
