"""Tests de la orquestación: troceo, verificación, deduplicación y avisos."""

from __future__ import annotations

from evidencia.extraccion import extraer, trocear
from evidencia.llm import ProveedorFalso
from evidencia.modelos import AfirmacionCruda, LoteCrudo, NivelAnclaje, TipoAfirmacion

TEXTO = (
    "El ministro Pérez anunció ayer que el PIB creció 4.1% en 2025. "
    "Creo que es una cifra inflada."
)


def lote(*crudas: AfirmacionCruda) -> LoteCrudo:
    return LoteCrudo(afirmaciones=list(crudas))


def cruda(texto: str, cita: str, tipo=TipoAfirmacion.HECHO_VERIFICABLE, verif=0.9):
    return AfirmacionCruda(texto=texto, cita=cita, tipo=tipo, verificabilidad=verif)


def test_afirmacion_bien_citada_se_acepta():
    proveedor = ProveedorFalso(
        lambda _: lote(
            cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025")
        )
    )
    resultado = extraer(TEXTO, proveedor)

    assert len(resultado.afirmaciones) == 1
    assert not resultado.rechazadas
    afirmacion = resultado.afirmaciones[0]
    assert TEXTO[afirmacion.inicio : afirmacion.fin] == afirmacion.cita


def test_afirmacion_inventada_se_rechaza_y_se_reporta():
    """El modelo puede alucinar; el sistema no lo publica ni lo esconde."""
    proveedor = ProveedorFalso(
        lambda _: lote(
            cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025"),
            cruda("El desempleo bajó a 5%", "el desempleo bajó a 5%"),
        )
    )
    resultado = extraer(TEXTO, proveedor)

    assert len(resultado.afirmaciones) == 1
    assert len(resultado.rechazadas) == 1
    assert resultado.rechazadas[0].texto == "El desempleo bajó a 5%"
    assert resultado.tasa_rechazo == 0.5


def test_solo_los_hechos_avanzan_a_la_fase_siguiente():
    proveedor = ProveedorFalso(
        lambda _: lote(
            cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025"),
            cruda(
                "El autor cree que la cifra está inflada",
                "Creo que es una cifra inflada",
                tipo=TipoAfirmacion.OPINION,
                verif=0.1,
            ),
        )
    )
    resultado = extraer(TEXTO, proveedor)

    assert len(resultado.afirmaciones) == 2  # la opinión se conserva, visible
    assert len(resultado.hechos) == 1  # pero no avanza


def test_duplicados_exactos_se_colapsan():
    repetida = cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025")
    proveedor = ProveedorFalso(lambda _: lote(repetida, repetida))
    assert len(extraer(TEXTO, proveedor).afirmaciones) == 1


def test_las_afirmaciones_se_ordenan_y_numeran_por_posicion():
    proveedor = ProveedorFalso(
        lambda _: lote(
            cruda(
                "El autor cree que la cifra está inflada",
                "Creo que es una cifra inflada",
                tipo=TipoAfirmacion.OPINION,
                verif=0.1,
            ),
            cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025"),
        )
    )
    resultado = extraer(TEXTO, proveedor)

    assert [a.id for a in resultado.afirmaciones] == ["c1", "c2"]
    assert resultado.afirmaciones[0].tipo is TipoAfirmacion.HECHO_VERIFICABLE
    assert resultado.afirmaciones[0].inicio < resultado.afirmaciones[1].inicio


def test_deixis_sin_resolver_genera_aviso():
    texto = "Él dijo que el precio subiría."
    proveedor = ProveedorFalso(lambda _: lote(cruda("Él dijo que el precio subiría", "Él dijo que el precio subiría")))
    afirmacion = extraer(texto, proveedor).afirmaciones[0]
    assert any("referencias sin resolver" in a for a in afirmacion.advertencias)


def test_anclaje_relajado_genera_aviso():
    proveedor = ProveedorFalso(
        lambda _: lote(cruda("El PIB creció 4.1% en 2025", "el PIB crecio 41 en 2025"))
    )
    afirmacion = extraer(TEXTO, proveedor).afirmaciones[0]
    assert afirmacion.nivel_anclaje is NivelAnclaje.RELAJADO
    assert any("reescribió" in a for a in afirmacion.advertencias)


def test_hecho_con_verificabilidad_muy_baja_genera_aviso():
    proveedor = ProveedorFalso(
        lambda _: lote(cruda("El PIB creció 4.1% en 2025", "el PIB creció 4.1% en 2025", verif=0.1))
    )
    afirmacion = extraer(TEXTO, proveedor).afirmaciones[0]
    assert any("verificabilidad muy baja" in a for a in afirmacion.advertencias)


def test_texto_corto_no_se_trocea():
    assert trocear("una frase corta", 6000) == [("una frase corta", 0)]


def test_troceo_conserva_las_posiciones_del_documento_completo():
    texto = "\n\n".join(f"Párrafo número {i} con algo de contenido." for i in range(40))
    fragmentos = trocear(texto, 200)

    assert len(fragmentos) > 1
    for fragmento, desplazamiento in fragmentos:
        assert texto[desplazamiento : desplazamiento + len(fragmento)] == fragmento


def test_offsets_de_texto_troceado_apuntan_al_documento_completo():
    relleno = "\n\n".join(f"Relleno {i} sin afirmaciones." for i in range(30))
    texto = f"{relleno}\n\nEl PIB creció 4.1% en 2025."

    def responder(fragmento):
        if "PIB" in fragmento:
            return lote(cruda("El PIB creció 4.1% en 2025", "El PIB creció 4.1% en 2025"))
        return lote()

    resultado = extraer(texto, ProveedorFalso(responder), max_caracteres=200)

    assert resultado.fragmentos > 1
    afirmacion = resultado.afirmaciones[0]
    assert texto[afirmacion.inicio : afirmacion.fin] == "El PIB creció 4.1% en 2025"


def test_lote_vacio_es_una_respuesta_valida():
    resultado = extraer("Qué día tan bonito.", ProveedorFalso(lambda _: lote()))
    assert resultado.afirmaciones == []
    assert resultado.tasa_rechazo == 0.0
