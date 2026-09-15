"""El anclaje es la regla dura del sistema. Estos tests son su red."""

from __future__ import annotations

import pytest

from evidencia.anclaje import anclar, huella
from evidencia.modelos import NivelAnclaje

FUENTE = (
    "El Banco Central informó que la inflación cerró 2025 en 3.2 %.\n"
    "Luego —según el informe— bajó."
)


def test_cita_literal_se_ancla_en_nivel_exacto():
    anclaje = anclar(FUENTE, "El Banco Central")
    assert anclaje is not None
    assert anclaje.nivel is NivelAnclaje.EXACTO
    assert FUENTE[anclaje.inicio : anclaje.fin] == "El Banco Central"


@pytest.mark.parametrize(
    "cita",
    [
        "LA INFLACIÓN CERRÓ 2025 EN 3.2 %",  # mayúsculas y espacio normal por duro
        "la inflacion cerro 2025 en 3.2 %",  # acentos perdidos
        "luego -según el informe- bajó",  # guiones largos por cortos
    ],
)
def test_variantes_tipograficas_se_anclan_normalizadas(cita):
    anclaje = anclar(FUENTE, cita)
    assert anclaje is not None
    assert anclaje.nivel is NivelAnclaje.NORMALIZADO


def test_el_texto_devuelto_es_el_original_no_el_del_modelo():
    """Lo que se guarda sale del texto de entrada, no de lo que escribió el modelo."""
    anclaje = anclar(FUENTE, "la inflacion cerro 2025 en 3.2 %")
    assert anclaje is not None
    assert anclaje.texto == "la inflación cerró 2025 en 3.2 %"
    assert anclaje.texto == FUENTE[anclaje.inicio : anclaje.fin]


def test_puntuacion_reescrita_cae_al_nivel_relajado():
    anclaje = anclar(FUENTE, "inflacion cerro 2025 en 32")
    assert anclaje is not None
    assert anclaje.nivel is NivelAnclaje.RELAJADO


def test_cita_inventada_se_rechaza():
    """El caso que justifica todo el módulo."""
    assert anclar(FUENTE, "el desempleo bajó a 5%") is None
    assert anclar(FUENTE, "El Banco Central desmintió el dato") is None


def test_cita_vacia_se_rechaza():
    assert anclar(FUENTE, "") is None
    assert anclar(FUENTE, "   \n  ") is None


def test_desplazamiento_se_suma_a_los_offsets():
    anclaje = anclar(FUENTE, "El Banco Central", desplazamiento=1000)
    assert anclaje is not None
    assert anclaje.inicio == 1000
    assert anclaje.fin == 1016


def test_cita_repetida_se_marca_ambigua():
    fuente = "Subió el precio. Subió el precio otra vez."
    anclaje = anclar(fuente, "Subió el precio")
    assert anclaje is not None
    assert anclaje.ambigua is True
    assert anclaje.inicio == 0


def test_cita_unica_no_se_marca_ambigua():
    anclaje = anclar(FUENTE, "El Banco Central")
    assert anclaje is not None
    assert anclaje.ambigua is False


def test_huella_ignora_forma_pero_no_contenido():
    assert huella("La Inflación, 3.2 %") == huella("la inflacion 32")
    assert huella("subió") != huella("bajó")
