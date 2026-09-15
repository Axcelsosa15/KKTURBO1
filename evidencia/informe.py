"""Renderizado del resultado.

El informe muestra los rechazos junto a los aciertos. Un extractor que
descarta en silencio es indistinguible de uno que no encuentra nada.
"""

from __future__ import annotations

from evidencia.modelos import ResultadoExtraccion, TipoAfirmacion

_ETIQUETAS = {
    TipoAfirmacion.HECHO_VERIFICABLE: "Hecho verificable",
    TipoAfirmacion.OPINION: "Opinión",
    TipoAfirmacion.PREDICCION: "Predicción",
    TipoAfirmacion.JUICIO_VALOR: "Juicio de valor",
}


def a_markdown(resultado: ResultadoExtraccion) -> str:
    lineas: list[str] = ["# Afirmaciones extraídas", ""]

    hechos = resultado.hechos
    lineas.append(
        f"{len(resultado.afirmaciones)} afirmaciones sobre {resultado.caracteres_entrada} "
        f"caracteres, de las cuales {len(hechos)} son verificables y pasan a la "
        f"búsqueda de evidencia."
    )
    lineas.append("")

    if not resultado.afirmaciones:
        lineas.append("_No se extrajo ninguna afirmación._")
    else:
        lineas.append("## Verificables")
        lineas.append("")
        if hechos:
            for afirmacion in hechos:
                lineas.extend(_bloque(afirmacion))
        else:
            lineas.append("_Ninguna._")
            lineas.append("")

        resto = [
            a
            for a in resultado.afirmaciones
            if a.tipo is not TipoAfirmacion.HECHO_VERIFICABLE
        ]
        if resto:
            lineas.append("## No verificables")
            lineas.append("")
            lineas.append(
                "Se listan para que veas qué se descartó y por qué, no para verificarlas."
            )
            lineas.append("")
            for afirmacion in resto:
                lineas.extend(_bloque(afirmacion))

    if resultado.rechazadas:
        lineas.append("## Rechazadas por el sistema")
        lineas.append("")
        lineas.append(
            "El modelo las propuso pero su cita no aparece en el texto de entrada, "
            "así que no se aceptan."
        )
        lineas.append("")
        for rechazada in resultado.rechazadas:
            lineas.append(f"- **{rechazada.texto}**")
            lineas.append(f"  - Cita propuesta: `{rechazada.cita_propuesta}`")
            lineas.append(f"  - Motivo: {rechazada.motivo}")
        lineas.append("")

    return "\n".join(lineas).rstrip() + "\n"


def _bloque(afirmacion) -> list[str]:
    etiqueta = _ETIQUETAS[afirmacion.tipo]
    lineas = [
        f"### `{afirmacion.id}` {afirmacion.texto}",
        "",
        f"- Tipo: {etiqueta} · verificabilidad {afirmacion.verificabilidad:.2f}",
        f"- Cita ({afirmacion.inicio}:{afirmacion.fin}, anclaje "
        f"{afirmacion.nivel_anclaje.value}): «{afirmacion.cita}»",
    ]
    if afirmacion.entidades:
        lineas.append(f"- Entidades: {', '.join(afirmacion.entidades)}")
    if afirmacion.cita_ambigua:
        lineas.append("- La cita aparece más de una vez; los offsets son de la primera.")
    for aviso in afirmacion.advertencias:
        lineas.append(f"- Aviso: {aviso}")
    lineas.append("")
    return lineas
