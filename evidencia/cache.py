"""Caché direccionada por contenido.

Sin esto, iterar sobre el prompt significa volver a pagar la extracción de
todo el set de evaluación en cada cambio. La clave incluye el modelo y la
versión del prompt, de modo que cambiar cualquiera de los dos es un fallo de
caché, no un resultado obsoleto servido en silencio.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from evidencia.modelos import LoteCrudo
from evidencia.prompts import VERSION_PROMPT

DIRECTORIO_POR_DEFECTO = Path(".cache/extraccion")

# Separador improbable dentro de un texto real, para que la concatenación de
# la clave no sea ambigua entre sus tres componentes.
_SEPARADOR = "\x1f"


class ProveedorConCache:
    """Envuelve un `ProveedorLLM` y persiste sus respuestas en disco."""

    def __init__(self, proveedor, directorio: Path | str = DIRECTORIO_POR_DEFECTO) -> None:
        self._proveedor = proveedor
        self.nombre = getattr(proveedor, "nombre", "desconocido")
        self.directorio = Path(directorio)
        self.aciertos = 0
        self.fallos = 0

    def _ruta(self, fragmento: str) -> Path:
        clave = _SEPARADOR.join([self.nombre, VERSION_PROMPT, fragmento])
        firma = hashlib.sha256(clave.encode("utf-8")).hexdigest()
        return self.directorio / f"{firma}.json"

    def extraer(self, fragmento: str) -> LoteCrudo:
        ruta = self._ruta(fragmento)
        if ruta.exists():
            self.aciertos += 1
            return LoteCrudo.model_validate_json(ruta.read_text(encoding="utf-8"))

        self.fallos += 1
        lote = self._proveedor.extraer(fragmento)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(lote.model_dump_json(indent=2), encoding="utf-8")
        return lote
