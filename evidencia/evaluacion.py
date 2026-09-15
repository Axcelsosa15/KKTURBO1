"""Arnés de evaluación de la Fase 1.

Mide los criterios de salida declarados en `docs/PLAN.md`. Sin esto, cada
cambio de prompt "parece" una mejora y nadie puede demostrarlo.

Los tres criterios:

- **Cobertura** de los hechos verificables que un humano identificó: >= 0.80.
- **Confusión de tipo**: enunciados que el humano marcó como opinión,
  predicción o juicio de valor y el sistema clasificó como hecho: < 0.10.
- **Validez de anclaje**: 1.00, sin excepciones. Cada cita guardada debe ser
  exactamente `texto[inicio:fin]`. Comprobable por código, no por criterio.

La sobre-extracción (afirmaciones que el sistema encuentra y el humano no
anotó) se reporta pero no se puntúa: casi siempre son afirmaciones reales que
se le pasaron al anotador, y castigarlas empujaría al sistema a extraer de
menos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from evidencia.anclaje import huella
from evidencia.extraccion import extraer
from evidencia.modelos import TipoAfirmacion

UMBRAL_COINCIDENCIA = 0.5

COBERTURA_MINIMA = 0.80
CONFUSION_MAXIMA = 0.10


@dataclass
class CasoEvaluacion:
    """Un documento anotado a mano."""

    id: str
    texto: str
    afirmaciones_oro: list[dict]
    notas: str = ""

    @property
    def hechos_oro(self) -> list[dict]:
        return [
            a
            for a in self.afirmaciones_oro
            if a["tipo"] == TipoAfirmacion.HECHO_VERIFICABLE.value
        ]

    @property
    def no_hechos_oro(self) -> list[dict]:
        return [
            a
            for a in self.afirmaciones_oro
            if a["tipo"] != TipoAfirmacion.HECHO_VERIFICABLE.value
        ]


@dataclass
class Resultados:
    """Métricas agregadas sobre todo el set."""

    casos: int = 0
    hechos_oro: int = 0
    hechos_cubiertos: int = 0
    no_hechos_oro: int = 0
    no_hechos_confundidos: int = 0
    anclajes: int = 0
    anclajes_validos: int = 0
    rechazadas: int = 0
    extraidas: int = 0
    por_nivel: dict[str, int] = field(default_factory=dict)
    sin_cubrir: list[tuple[str, str]] = field(default_factory=list)

    @property
    def cobertura(self) -> float:
        return self.hechos_cubiertos / self.hechos_oro if self.hechos_oro else 1.0

    @property
    def confusion(self) -> float:
        return (
            self.no_hechos_confundidos / self.no_hechos_oro if self.no_hechos_oro else 0.0
        )

    @property
    def validez_anclaje(self) -> float:
        return self.anclajes_validos / self.anclajes if self.anclajes else 1.0

    @property
    def aprueba(self) -> bool:
        return (
            self.cobertura >= COBERTURA_MINIMA
            and self.confusion < CONFUSION_MAXIMA
            and self.validez_anclaje == 1.0
        )


def _palabras(texto: str) -> list[str]:
    """Palabras canónicas: sin acentos, sin mayúsculas, sin puntuación."""
    return [huella(p) for p in texto.split() if huella(p)]


def parecido(uno: str, otro: str) -> float:
    """Jaccard sobre palabras canónicas.

    Se compara así, y no por igualdad, porque dos redacciones correctas de la
    misma afirmación casi nunca coinciden palabra por palabra.
    """
    a, b = set(_palabras(uno)), set(_palabras(otro))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cargar_set(ruta: Path | str) -> list[CasoEvaluacion]:
    casos: list[CasoEvaluacion] = []
    for numero, linea in enumerate(Path(ruta).read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("//"):
            continue
        try:
            datos = json.loads(linea)
        except json.JSONDecodeError as error:
            raise ValueError(f"{ruta}:{numero} no es JSON válido: {error}") from error
        casos.append(
            CasoEvaluacion(
                id=datos["id"],
                texto=datos["texto"],
                afirmaciones_oro=datos.get("afirmaciones_oro", []),
                notas=datos.get("notas", ""),
            )
        )
    return casos


def evaluar(casos: list[CasoEvaluacion], proveedor) -> Resultados:
    resultados = Resultados(casos=len(casos))

    for caso in casos:
        extraccion = extraer(caso.texto, proveedor)
        resultados.extraidas += len(extraccion.afirmaciones)
        resultados.rechazadas += len(extraccion.rechazadas)

        # Criterio 3: el anclaje debe reproducir el texto original por offsets.
        for afirmacion in extraccion.afirmaciones:
            resultados.anclajes += 1
            if caso.texto[afirmacion.inicio : afirmacion.fin] == afirmacion.cita:
                resultados.anclajes_validos += 1
            nivel = afirmacion.nivel_anclaje.value
            resultados.por_nivel[nivel] = resultados.por_nivel.get(nivel, 0) + 1

        hechos = extraccion.hechos

        # Criterio 1: cobertura de los hechos anotados a mano.
        for oro in caso.hechos_oro:
            resultados.hechos_oro += 1
            if any(parecido(oro["texto"], a.texto) >= UMBRAL_COINCIDENCIA for a in hechos):
                resultados.hechos_cubiertos += 1
            else:
                resultados.sin_cubrir.append((caso.id, oro["texto"]))

        # Criterio 2: opiniones y predicciones que se colaron como hechos.
        for oro in caso.no_hechos_oro:
            resultados.no_hechos_oro += 1
            if any(parecido(oro["texto"], a.texto) >= UMBRAL_COINCIDENCIA for a in hechos):
                resultados.no_hechos_confundidos += 1

    return resultados


def a_texto(resultados: Resultados) -> str:
    def marca(ok: bool) -> str:
        return "PASA" if ok else "FALLA"

    lineas = [
        f"Casos evaluados: {resultados.casos}",
        f"Afirmaciones extraídas: {resultados.extraidas} "
        f"(rechazadas por anclaje: {resultados.rechazadas})",
        "",
        f"[{marca(resultados.cobertura >= COBERTURA_MINIMA)}] "
        f"Cobertura de hechos: {resultados.cobertura:.0%} "
        f"({resultados.hechos_cubiertos}/{resultados.hechos_oro}, mínimo {COBERTURA_MINIMA:.0%})",
        f"[{marca(resultados.confusion < CONFUSION_MAXIMA)}] "
        f"Confusión de tipo: {resultados.confusion:.0%} "
        f"({resultados.no_hechos_confundidos}/{resultados.no_hechos_oro}, máximo {CONFUSION_MAXIMA:.0%})",
        f"[{marca(resultados.validez_anclaje == 1.0)}] "
        f"Validez de anclaje: {resultados.validez_anclaje:.0%} "
        f"({resultados.anclajes_validos}/{resultados.anclajes}, exigido 100%)",
    ]

    if resultados.por_nivel:
        reparto = ", ".join(
            f"{nivel}: {conteo}" for nivel, conteo in sorted(resultados.por_nivel.items())
        )
        lineas += ["", f"Anclajes por nivel: {reparto}"]
        relajados = resultados.por_nivel.get("relajado", 0)
        if relajados:
            lineas.append(
                f"  Aviso: {relajados} cita(s) solo coinciden ignorando puntuación. "
                "El modelo está reescribiendo en vez de copiar; revisa el prompt."
            )

    if resultados.sin_cubrir:
        lineas += ["", "Hechos anotados que el sistema no encontró:"]
        lineas += [f"  [{caso}] {texto}" for caso, texto in resultados.sin_cubrir]

    lineas += ["", f"Resultado: la Fase 1 {'PASA' if resultados.aprueba else 'NO PASA'}."]
    return "\n".join(lineas)
