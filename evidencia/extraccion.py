"""Orquestación de la Fase 1.

Trocea el texto, pide la extracción al proveedor, y somete cada afirmación a
la verificación de anclaje. Lo que no se ancla, no pasa: esa es la frontera
entre lo que el modelo dice y lo que el sistema acepta.
"""

from __future__ import annotations

import re

from evidencia.anclaje import anclar, huella
from evidencia.modelos import (
    Afirmacion,
    AfirmacionCruda,
    AfirmacionRechazada,
    NivelAnclaje,
    ResultadoExtraccion,
    TipoAfirmacion,
)

MAX_CARACTERES_FRAGMENTO = 6000

# Términos que delatan una afirmación que no se sostiene sola: sin el texto
# alrededor no se sabe a qué o a quién se refieren. No se rechaza por esto
# (a veces el contexto no permite resolverlo), pero se marca.
_DEIXIS = {
    "él", "ella", "ellos", "ellas", "esto", "eso", "aquello", "aquel",
    "allí", "allá", "ahí", "ayer", "hoy", "mañana", "anoche", "entonces",
    "dicho", "dicha", "dichos", "dichas", "este", "esta", "estos", "estas",
    "ese", "esa", "esos", "esas",
}
_PALABRAS = re.compile(r"[^\W\d_]+", re.UNICODE)


def trocear(
    texto: str, max_caracteres: int = MAX_CARACTERES_FRAGMENTO
) -> list[tuple[str, int]]:
    """Parte el texto en fragmentos, devolviendo cada uno con su desplazamiento.

    Corta por párrafos y, dentro de un párrafo largo, por frases. El
    desplazamiento es lo que permite que los offsets de una cita sigan
    refiriéndose al documento completo y no al trozo.
    """
    if len(texto) <= max_caracteres:
        return [(texto, 0)]

    piezas: list[tuple[str, int]] = []
    for coincidencia in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]*)*", texto):
        bloque, inicio = coincidencia.group(), coincidencia.start()
        if len(bloque) <= max_caracteres:
            piezas.append((bloque, inicio))
            continue
        # Párrafo demasiado largo: cortar por final de frase.
        cursor = 0
        for frase in re.finditer(r".{1,%d}(?:[.!?](?=\s)|$)" % max_caracteres, bloque, re.S):
            if frase.group().strip():
                piezas.append((frase.group(), inicio + frase.start()))
            cursor = frase.end()
        if cursor < len(bloque):  # resto sin puntuación final
            piezas.append((bloque[cursor:], inicio + cursor))

    fragmentos: list[tuple[str, int]] = []
    actual, desplazamiento = "", 0
    for bloque, inicio in piezas:
        if not actual:
            actual, desplazamiento = bloque, inicio
        elif inicio + len(bloque) - desplazamiento <= max_caracteres:
            actual = texto[desplazamiento : inicio + len(bloque)]
        else:
            fragmentos.append((actual, desplazamiento))
            actual, desplazamiento = bloque, inicio
    if actual:
        fragmentos.append((actual, desplazamiento))

    return fragmentos or [(texto, 0)]


def _advertencias(cruda: AfirmacionCruda, nivel: NivelAnclaje) -> list[str]:
    avisos: list[str] = []

    palabras = {p.casefold() for p in _PALABRAS.findall(cruda.texto)}
    deicticos = sorted(palabras & _DEIXIS)
    if deicticos:
        avisos.append(
            "La afirmación puede no sostenerse fuera de su contexto "
            f"(referencias sin resolver: {', '.join(deicticos)})."
        )

    if nivel is NivelAnclaje.RELAJADO:
        avisos.append(
            "La cita solo coincide ignorando puntuación y espacios; "
            "el modelo la reescribió en vez de copiarla."
        )

    if cruda.tipo is TipoAfirmacion.HECHO_VERIFICABLE and cruda.verificabilidad < 0.3:
        avisos.append(
            "Marcada como hecho verificable pero con verificabilidad muy baja; "
            "probablemente no haya fuente pública."
        )

    return avisos


def extraer(
    texto: str,
    proveedor,
    max_caracteres: int = MAX_CARACTERES_FRAGMENTO,
) -> ResultadoExtraccion:
    """Extrae y verifica las afirmaciones de `texto`."""
    fragmentos = trocear(texto, max_caracteres)
    resultado = ResultadoExtraccion(
        caracteres_entrada=len(texto), fragmentos=len(fragmentos)
    )

    vistas: set[tuple[str, int, int]] = set()

    for fragmento, desplazamiento in fragmentos:
        lote = proveedor.extraer(fragmento)

        for cruda in lote.afirmaciones:
            anclaje = anclar(fragmento, cruda.cita, desplazamiento)

            if anclaje is None:
                resultado.rechazadas.append(
                    AfirmacionRechazada(
                        texto=cruda.texto,
                        cita_propuesta=cruda.cita,
                        motivo="La cita no aparece en el texto de entrada.",
                    )
                )
                continue

            clave = (huella(cruda.texto), anclaje.inicio, anclaje.fin)
            if clave in vistas:
                continue
            vistas.add(clave)

            resultado.afirmaciones.append(
                Afirmacion(
                    id=f"c{len(resultado.afirmaciones) + 1}",
                    texto=cruda.texto,
                    tipo=cruda.tipo,
                    entidades=cruda.entidades,
                    verificabilidad=cruda.verificabilidad,
                    cita=anclaje.texto,
                    inicio=anclaje.inicio,
                    fin=anclaje.fin,
                    nivel_anclaje=anclaje.nivel,
                    cita_ambigua=anclaje.ambigua,
                    advertencias=_advertencias(cruda, anclaje.nivel),
                )
            )

    resultado.afirmaciones.sort(key=lambda a: (a.inicio, a.fin))
    for indice, afirmacion in enumerate(resultado.afirmaciones, start=1):
        afirmacion.id = f"c{indice}"

    return resultado
