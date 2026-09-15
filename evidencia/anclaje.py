"""Anclaje de citas al texto original.

El problema: se le pide al modelo que copie un fragmento literal, y devuelve
algo *casi* literal — comillas curvas por rectas, un guión largo por uno corto,
saltos de línea colapsados, un acento perdido. Un `str.find` falla y se
descartaría una afirmación buena. Aceptar la cita del modelo sin verificar es
el otro extremo: abre la puerta a que invente texto que nadie escribió.

La solución es normalizar manteniendo un mapa de offsets reversible, buscar en
el espacio normalizado y **recuperar el substring original** por sus índices.
Lo que se guarda nunca es lo que escribió el modelo: es lo que hay en el texto.

Tres niveles, en orden de exigencia decreciente:

1. `EXACTO`      — coincidencia byte a byte.
2. `NORMALIZADO` — ignora mayúsculas, acentos, variantes tipográficas y
                   espaciado. Es el caso normal.
3. `RELAJADO`    — ignora además toda la puntuación y los espacios. Último
                   recurso; si aparece mucho, el prompt está fallando.

Si los tres fallan, la afirmación se rechaza. Sin excepciones.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from evidencia.modelos import NivelAnclaje

# Variantes tipográficas que un modelo intercambia sin darse cuenta.
_EQUIVALENCIAS: dict[str, str] = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-",
    "…": "...",
    " ": " ", " ": " ", " ": " ", " ": " ",
}


@dataclass(frozen=True)
class Anclaje:
    """Una cita localizada en el texto original."""

    inicio: int
    fin: int
    texto: str
    nivel: NivelAnclaje
    ambigua: bool


def _normalizar(texto: str, agresivo: bool = False) -> tuple[str, list[int]]:
    """Normaliza devolviendo, por cada carácter de salida, su índice de origen.

    El mapa es lo que hace reversible la operación: sin él se podría comprobar
    que la cita existe, pero no de dónde sale, y habría que confiar en la copia
    del modelo.

    Con `agresivo=True` elimina además puntuación y espacios (nivel RELAJADO).
    """
    salida: list[str] = []
    mapa: list[int] = []
    en_espacio = False

    for i, caracter in enumerate(texto):
        # Caracteres de formato invisibles (zero-width, marcas de dirección).
        if unicodedata.category(caracter) == "Cf":
            continue

        if caracter.isspace():
            if agresivo or en_espacio:
                continue
            salida.append(" ")
            mapa.append(i)
            en_espacio = True
            continue

        en_espacio = False
        equivalente = _EQUIVALENCIAS.get(caracter, caracter)

        # Descomponer y descartar marcas diacríticas: "inflación" == "inflacion".
        descompuesto = unicodedata.normalize("NFD", equivalente)
        sin_acentos = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
        plegado = sin_acentos.casefold()

        for c in plegado:
            if agresivo and not c.isalnum():
                continue
            salida.append(c)
            mapa.append(i)

    return "".join(salida), mapa


def _buscar_en_nivel(
    fuente: str, cita: str, nivel: NivelAnclaje
) -> Anclaje | None:
    agresivo = nivel is NivelAnclaje.RELAJADO
    normalizada_fuente, mapa = _normalizar(fuente, agresivo)
    normalizada_cita, _ = _normalizar(cita, agresivo)
    normalizada_cita = normalizada_cita.strip()

    if not normalizada_cita:
        return None

    posicion = normalizada_fuente.find(normalizada_cita)
    if posicion == -1:
        return None

    ambigua = normalizada_fuente.find(normalizada_cita, posicion + 1) != -1
    inicio = mapa[posicion]
    fin = mapa[posicion + len(normalizada_cita) - 1] + 1
    return Anclaje(inicio, fin, fuente[inicio:fin], nivel, ambigua)


def anclar(fuente: str, cita: str, desplazamiento: int = 0) -> Anclaje | None:
    """Localiza `cita` dentro de `fuente`, o devuelve `None` si no está.

    `desplazamiento` suma a los offsets para que un fragmento de un texto
    troceado reporte posiciones del documento completo.
    """
    if not cita or not cita.strip():
        return None

    # Nivel 1: coincidencia literal. El caso feliz, y el más barato.
    posicion = fuente.find(cita)
    if posicion != -1:
        ambigua = fuente.find(cita, posicion + 1) != -1
        return Anclaje(
            posicion + desplazamiento,
            posicion + len(cita) + desplazamiento,
            cita,
            NivelAnclaje.EXACTO,
            ambigua,
        )

    # Niveles 2 y 3.
    for nivel in (NivelAnclaje.NORMALIZADO, NivelAnclaje.RELAJADO):
        encontrado = _buscar_en_nivel(fuente, cita, nivel)
        if encontrado is not None:
            return Anclaje(
                encontrado.inicio + desplazamiento,
                encontrado.fin + desplazamiento,
                encontrado.texto,
                nivel,
                encontrado.ambigua,
            )

    return None


def huella(texto: str) -> str:
    """Forma canónica de un texto, para comparar o deduplicar.

    Ignora mayúsculas, acentos, puntuación y espaciado: dos redacciones que
    solo difieren en eso producen la misma huella.
    """
    normalizado, _ = _normalizar(texto, agresivo=True)
    return normalizado
