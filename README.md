# evidencia

Herramienta personal para leer con más criterio: pegas un texto y te devuelve
las afirmaciones verificables que contiene, cada una anclada a su cita literal.

**No decide si algo es verdad.** No existe un veredicto `verdadero/falso` en
ninguna parte del sistema, y es deliberado: un clasificador de veracidad
aprende estilo, no hechos, y un falso positivo —marcar como falso algo cierto—
hace más daño que no detectar nada. El diseño completo y sus no-objetivos están
en [`docs/PLAN.md`](docs/PLAN.md).

## Estado

| Fase | Qué hace | Estado |
|---|---|---|
| 0 | Set de evaluación anotado a mano | Semilla de ejemplo, **pendiente de datos reales** |
| 1 | Extracción de afirmaciones y anclaje de citas | Implementada |
| 2 | Recuperación de evidencia | Pendiente |
| 3 | Postura e informe con fuentes | Pendiente |
| 4 | Interfaz | Pendiente |

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Las llamadas al modelo necesitan credenciales de la API de Claude: exporta
`ANTHROPIC_API_KEY`, o inicia sesión con `ant auth login` (el SDK recoge el
perfil automáticamente).

## Uso

```bash
# Desde un archivo
evidencia extraer articulo.txt

# Desde stdin
pbpaste | evidencia extraer

# JSON, para encadenar con otra cosa
evidencia extraer articulo.txt --formato json
```

Salida abreviada:

```
### `c1` El ministro Pérez anunció que el PIB creció 4.1% en 2025

- Tipo: Hecho verificable · verificabilidad 0.95
- Cita (0:61, anclaje exacto): «El ministro Pérez anunció ayer que el PIB creció 4.1% en 2025»

## Rechazadas por el sistema

- **El Banco Mundial desmintió el dato**
  - Motivo: La cita no aparece en el texto de entrada.
```

Las respuestas se cachean en `.cache/extraccion/`, con el modelo y la versión
del prompt dentro de la clave. Iterar sobre el prompt no cuesta dinero dos
veces, y cambiarlo nunca sirve un resultado viejo en silencio.

## La regla que sostiene todo: el anclaje

Cada afirmación que el sistema acepta lleva una cita que **existe literalmente
en el texto de entrada**, recuperada por offsets. Lo que se guarda nunca es lo
que escribió el modelo: es el substring original, verificado.

El modelo devuelve citas *casi* literales — comillas curvas por rectas, un
acento perdido, saltos de línea colapsados. Un `str.find` fallaría y
descartaría afirmaciones buenas; aceptar la cita sin verificar abriría la
puerta a texto inventado. `evidencia/anclaje.py` resuelve esto normalizando con
un mapa de offsets reversible, en tres niveles:

| Nivel | Qué tolera | Qué significa |
|---|---|---|
| `exacto` | nada | El modelo copió bien |
| `normalizado` | mayúsculas, acentos, comillas, guiones, espaciado | Caso normal |
| `relajado` | además, toda la puntuación | El modelo reescribió: revisa el prompt |

Si los tres fallan, la afirmación se **rechaza** y aparece en el informe como
rechazada. Descartar en silencio sería indistinguible de no encontrar nada.

## Evaluar

```bash
evidencia evaluar
```

Mide los tres criterios de salida de la Fase 1 y devuelve código de salida 1 si
alguno falla:

- **Cobertura** de los hechos que un humano anotó: >= 80%
- **Confusión de tipo** (opiniones o predicciones coladas como hechos): < 10%
- **Validez de anclaje**: 100%, comprobando que `texto[inicio:fin] == cita`

La sobre-extracción se reporta pero no puntúa: castigarla empujaría al sistema
a extraer de menos.

### Antes de creerte los números

El set en `eval/extraccion.jsonl` es una **semilla sintética** que ejercita el
arnés y enseña el formato. No mide nada útil: está escrito por la misma lógica
que construyó el extractor.

Para que sirva hay que reemplazarlo por 50-100 documentos reales que tú
consumes, anotados por ti, incluyendo los casos difíciles. Instrucciones y
formato en [`eval/README.md`](eval/README.md). Es la parte del proyecto que
ningún automatismo puede hacer por ti, y sin ella cada cambio de prompt solo
*parece* una mejora.

## Estructura

```
evidencia/
  modelos.py      Modelos de dominio. Separa lo que dice el modelo de lo que se acepta
  anclaje.py      Verificación de citas en tres niveles con mapa de offsets
  prompts.py      Prompt de extracción, versionado para la clave de caché
  llm.py          Proveedor tras un Protocol: Anthropic, y uno falso para tests
  cache.py        Caché direccionada por contenido
  extraccion.py   Troceo, verificación, deduplicación y avisos
  evaluacion.py   Arnés de métricas de la Fase 1
  informe.py      Renderizado a markdown
  cli.py          Línea de comandos
eval/             Set anotado (semilla) y su formato
tests/            Suite de pytest, corre sin red ni credenciales
docs/PLAN.md      Diseño, fases, métricas y riesgos
```

## Tests

```bash
.venv/bin/python -m pytest
```

Corren sin red y sin credenciales: el proveedor del modelo está tras un
`Protocol` y los tests usan una implementación falsa y determinista.

## Límite conocido

Una afirmación engañosa pero técnicamente cierta —un porcentaje sin
denominador, un dato real de un período escogido a conveniencia— se extraerá
como un hecho verificable normal, y la Fase 3 la marcará como apoyada por la
evidencia. El sistema no lo detecta. Está documentado en `docs/PLAN.md` en
lugar de disimulado.
