# Plan: Sistema de trazabilidad de evidencia

## 1. Qué es y qué no es

**Es**: una herramienta personal que, dado un texto, extrae las afirmaciones
verificables, busca evidencia, y devuelve un informe donde cada afirmación
aparece con su evidencia, la cita textual y el enlace.

**No es** un detector de verdad. El sistema nunca emite un veredicto
`verdadero/falso` como salida principal. La decisión final es del humano.

### No-objetivos explícitos

Declarados aquí para no reabrirlos cada semana:

- No se entrena un clasificador `texto -> falso/verdadero`. Ese enfoque aprende
  estilo (sensacionalismo, ortografía, longitud), no veracidad, y se desploma
  fuera de su distribución de entrenamiento.
- No se usan listas negras de dominios como veredicto. Como mucho, como señal
  secundaria visible al usuario. La procedencia no es veracidad.
- No se le pregunta al modelo "¿esto es cierto?" sin recuperación de evidencia.
  Sin fuentes, la respuesta es alucinación con tono seguro.
- No se oculta ni descarta contenido. El sistema informa, no filtra.

## 2. Reglas duras de diseño

1. **Ningún veredicto sin cita.** Toda postura (apoya / contradice) debe llevar
   un fragmento textual literal de la fuente y una URL. Si no hay cita, la
   salida es `evidencia_insuficiente`.
2. **`evidencia_insuficiente` es una salida de primera clase**, no un error.
   Se espera que sea frecuente.
3. **Toda afirmación extraída debe existir literalmente en el texto de entrada**
   (se guarda el fragmento original). Esto corta la fabricación de afirmaciones.
4. **Separar hecho verificable de opinión, predicción y juicio de valor.**
   Solo lo primero entra al pipeline de evidencia.
5. **La incertidumbre se muestra, no se redondea.** Nada de convertir "dos
   fuentes débiles" en un check verde.

## 3. Arquitectura

```
Texto de entrada
      |
      v
[1] Extracción de afirmaciones  -> lista de claims con span original
      |
      v
[2] Priorización                -> cuáles merecen búsqueda (coste)
      |
      v
[3] Recuperación de evidencia   -> búsqueda + fuentes primarias
      |
      v
[4] Evaluación de postura       -> apoya / contradice / no relacionado
      |
      v
[5] Informe                     -> markdown o JSON, con enlaces y citas
```

### Contratos de datos

Fijarlos ahora permite construir y probar cada etapa por separado.

```json
// Salida de [1] Extracción
{
  "id": "c1",
  "texto": "La inflación en RD cerró 2025 en 3.2%",
  "span_original": "...cita literal del texto de entrada...",
  "tipo": "hecho_verificable",        // hecho_verificable | opinion | prediccion | juicio_valor
  "entidades": ["República Dominicana", "inflación", "2025"],
  "verificabilidad": 0.9              // 0-1, usado por [2]
}
```

```json
// Salida de [3] Recuperación
{
  "claim_id": "c1",
  "fuentes": [{
    "url": "https://...",
    "titulo": "...",
    "fecha": "2026-01-15",
    "tipo_fuente": "primaria",        // primaria | secundaria | agregador | desconocida
    "extracto": "...texto literal relevante..."
  }]
}
```

```json
// Salida de [4] Postura
{
  "claim_id": "c1",
  "postura": "apoyada",               // apoyada | contradicha | evidencia_insuficiente
  "confianza": 0.8,
  "citas": [{"url": "https://...", "texto": "...literal..."}],
  "nota": "La fuente usa un periodo distinto (año fiscal vs. calendario)"
}
```

## 4. Fases

### Fase 0 — Set de evaluación (ANTES de cualquier pipeline)

La fase que casi todos se saltan y la que decide si el proyecto sirve.

Construir a mano 50-100 afirmaciones reales, de fuentes reales que uno consume,
etiquetadas manualmente. Debe incluir a propósito los cuatro casos difíciles:

- Ciertas pero que suenan falsas.
- Falsas pero que suenan creíbles.
- Engañosas pero técnicamente ciertas (el caso más duro; ver Riesgos).
- Sin evidencia pública disponible.

Formato: `eval/extraccion.jsonl`, un documento anotado por línea. El esquema
exacto y el procedimiento están en `eval/README.md`.

**Criterio de salida**: 50 documentos anotados, con al menos 10 de cada
categoría difícil.

**Estado**: el repositorio trae una semilla sintética de 8 casos que ejercita el
arnés y enseña el formato. No mide nada: hay que reemplazarla por documentos
reales.

### Fase 1 — Extracción de afirmaciones

**Estado: implementada.** `evidencia extraer` acepta texto por stdin o archivo
y emite markdown o JSON. El arnés de métricas es `evidencia evaluar`.

**Criterio de salida**, medido contra el set de Fase 0:
- Se extraen >= 80% de las afirmaciones verificables que un humano identifica.
- < 10% de opiniones/predicciones clasificadas erróneamente como hecho.
- 100% de los `span_original` existen literalmente en el texto de entrada
  (verificable por código, no por juicio).

Los tres los mide `evidencia evaluar`, que devuelve código de salida 1 si
alguno falla. El tercero se comprueba afirmación por afirmación contrastando
`texto[inicio:fin]` con la cita guardada.

### Fase 2 — Recuperación de evidencia

Búsqueda por afirmación, con preferencia por fuentes primarias (datos
oficiales, papers, registros) sobre secundarias y agregadores.

**Criterio de salida**:
- >= 70% de las afirmaciones del set obtienen al menos una fuente relevante.
- Detección de circularidad: no contar N copias del mismo teletipo como N
  fuentes independientes.
- Coste y latencia medidos y registrados por ejecución.

### Fase 3 — Postura e informe

**Criterio de salida**, la métrica que manda:
- **Precisión en `contradicha` >= 90%.** Es decir: cuando el sistema dice que
  algo está contradicho por la evidencia, acierta 9 de cada 10 veces. Un falso
  positivo aquí es el daño real del proyecto.
- 100% de posturas no-insuficientes llevan cita literal + URL.
- El informe es legible de un vistazo.

### Fase 4 — Interfaz

Solo si las Fases 1-3 pasan sus criterios. Antes de eso, una UI bonita sobre un
pipeline malo solo sirve para confiar en resultados que no lo merecen.

## 5. Métricas

Las que importan:

| Métrica | Por qué |
|---|---|
| Precisión en `contradicha` | Los falsos positivos son el daño del sistema |
| Cobertura de afirmaciones | Cuántas afirmaciones reales llega a procesar |
| % de veredictos con cita verificable | Mide honestidad del output |
| Tasa de `evidencia_insuficiente` | Si es 0%, el sistema está mintiendo |
| Coste y latencia por texto | Decide si es usable a diario |

**No se usa "accuracy" global.** Con clases desbalanceadas y una salida
`evidencia_insuficiente` frecuente, es una métrica que oculta el fallo que
importa.

## 6. Riesgos conocidos

1. **Fabricación de afirmaciones.** El modelo extrae algo que no está en el
   texto. *Mitigación*: exigir y verificar por código el span literal.
2. **Circularidad de fuentes.** Veinte medios reproduciendo el mismo teletipo
   parecen veinte confirmaciones. *Mitigación*: deduplicar por contenido,
   priorizar fuente primaria, mostrar el conteo de fuentes independientes.
3. **Engañoso pero técnicamente cierto.** El sistema lo marcará como `apoyada`.
   Es un límite real del enfoque. *Mitigación*: no ocultarlo — documentarlo y
   usar el campo `nota` para señalar contexto faltante (periodo, denominador,
   cherry-picking).
4. **Sesgo del modelo en temas polarizados.** *Mitigación*: el informe expone
   las fuentes, el usuario juzga. Es otra razón para no dar veredicto final.
5. **Coste y latencia.** Cada afirmación implica búsquedas y llamadas al
   modelo. *Mitigación*: la etapa [2] de priorización, y caché por afirmación.
6. **Deriva de la fuente de búsqueda.** El proveedor cambia resultados o
   precios. *Mitigación*: aislar la búsqueda tras una interfaz.

## 7. Asunciones (a confirmar)

Se asume lo siguiente para poder avanzar; cualquiera es revisable:

- **Lenguaje**: Python 3.11+, sin framework web al inicio. CLI primero.
- **Modelo**: API de Claude para extracción y postura.
- **Búsqueda**: pendiente de elegir proveedor (Brave / Tavily / SerpAPI u otro).
  Se aisla tras una interfaz para poder cambiarlo sin tocar el resto.
- **Modelo**: `claude-opus-5` con razonamiento adaptativo y salida estructurada.
  El proveedor vive tras un `Protocol`, así que cambiarlo no toca el pipeline.
- **Idioma de entrada**: español e inglés.
- **Ejecución**: local, sin base de datos al inicio (archivos JSON + caché).
