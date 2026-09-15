"""Tests del arnés: si mide mal, todas las decisiones posteriores son ruido."""

from __future__ import annotations

from pathlib import Path

from evidencia.cache import ProveedorConCache
from evidencia.evaluacion import (
    CasoEvaluacion,
    cargar_set,
    evaluar,
    parecido,
)
from evidencia.llm import ProveedorFalso
from evidencia.modelos import AfirmacionCruda, LoteCrudo, TipoAfirmacion

TEXTO = "El PIB creció 4.1% en 2025. Creo que es una cifra inflada."

CASO = CasoEvaluacion(
    id="t1",
    texto=TEXTO,
    afirmaciones_oro=[
        {"texto": "El PIB creció 4.1% en 2025", "tipo": "hecho_verificable"},
        {"texto": "El autor cree que la cifra está inflada", "tipo": "opinion"},
    ],
)


def cruda(texto, cita, tipo=TipoAfirmacion.HECHO_VERIFICABLE, verif=0.9):
    return AfirmacionCruda(texto=texto, cita=cita, tipo=tipo, verificabilidad=verif)


def test_parecido_tolera_redaccion_distinta_pero_no_sentido_distinto():
    assert parecido("El PIB creció 4.1% en 2025", "el pib crecio 4.1 % en 2025") > 0.9
    assert parecido("El PIB creció en 2025", "El desempleo bajó en 2024") < 0.5


def test_extraccion_correcta_aprueba_los_tres_criterios():
    proveedor = ProveedorFalso(
        lambda _: LoteCrudo(
            afirmaciones=[
                cruda("El PIB creció 4.1% en 2025", "El PIB creció 4.1% en 2025"),
                cruda(
                    "El autor cree que la cifra está inflada",
                    "Creo que es una cifra inflada",
                    tipo=TipoAfirmacion.OPINION,
                    verif=0.1,
                ),
            ]
        )
    )
    resultados = evaluar([CASO], proveedor)

    assert resultados.cobertura == 1.0
    assert resultados.confusion == 0.0
    assert resultados.validez_anclaje == 1.0
    assert resultados.aprueba


def test_hecho_no_encontrado_baja_la_cobertura_y_se_reporta():
    proveedor = ProveedorFalso(lambda _: LoteCrudo(afirmaciones=[]))
    resultados = evaluar([CASO], proveedor)

    assert resultados.cobertura == 0.0
    assert not resultados.aprueba
    assert resultados.sin_cubrir == [("t1", "El PIB creció 4.1% en 2025")]


def test_opinion_clasificada_como_hecho_cuenta_como_confusion():
    proveedor = ProveedorFalso(
        lambda _: LoteCrudo(
            afirmaciones=[
                cruda("El PIB creció 4.1% en 2025", "El PIB creció 4.1% en 2025"),
                cruda(
                    "El autor cree que la cifra está inflada",
                    "Creo que es una cifra inflada",
                ),  # tipo incorrecto a propósito
            ]
        )
    )
    resultados = evaluar([CASO], proveedor)

    assert resultados.cobertura == 1.0
    assert resultados.confusion == 1.0
    assert not resultados.aprueba


def test_sobreextraccion_no_penaliza():
    """Castigarla empujaría al sistema a extraer de menos."""
    proveedor = ProveedorFalso(
        lambda _: LoteCrudo(
            afirmaciones=[
                cruda("El PIB creció 4.1% en 2025", "El PIB creció 4.1% en 2025"),
                cruda("La cifra corresponde al año 2025", "en 2025"),
                cruda(
                    "El autor cree que la cifra está inflada",
                    "Creo que es una cifra inflada",
                    tipo=TipoAfirmacion.OPINION,
                    verif=0.1,
                ),
            ]
        )
    )
    resultados = evaluar([CASO], proveedor)

    assert resultados.extraidas == 3
    assert resultados.aprueba


def test_cargar_el_set_semilla_del_repositorio():
    casos = cargar_set(Path(__file__).resolve().parents[1] / "eval" / "extraccion.jsonl")
    assert len(casos) >= 8
    assert all(caso.texto.strip() for caso in casos)
    tipos = {a["tipo"] for caso in casos for a in caso.afirmaciones_oro}
    assert tipos <= {t.value for t in TipoAfirmacion}


def test_la_cache_evita_la_segunda_llamada(tmp_path):
    interno = ProveedorFalso(
        lambda _: LoteCrudo(
            afirmaciones=[cruda("El PIB creció 4.1% en 2025", "El PIB creció 4.1% en 2025")]
        ),
        nombre="modelo-de-prueba",
    )
    cacheado = ProveedorConCache(interno, tmp_path / "cache")

    primero = evaluar([CASO], cacheado)
    segundo = evaluar([CASO], cacheado)

    assert len(interno.llamadas) == 1
    assert cacheado.aciertos == 1 and cacheado.fallos == 1
    assert primero.cobertura == segundo.cobertura
