# Set de evaluación

`extraccion.jsonl` evalúa la **Fase 1**: ¿el sistema encuentra las afirmaciones
que un humano encuentra, y las clasifica bien?

Cada línea es un documento anotado a mano:

```json
{
  "id": "s1",
  "texto": "el texto completo tal cual",
  "notas": "por qué este caso es interesante",
  "afirmaciones_oro": [
    {"texto": "afirmación autocontenida", "tipo": "hecho_verificable"}
  ]
}
```

`tipo` es uno de `hecho_verificable`, `opinion`, `prediccion`, `juicio_valor`.

## Lo que hay aquí ahora es una semilla, no un set de evaluación

Los casos incluidos son ejemplos sintéticos escritos para ejercitar el arnés y
enseñar el formato. **No sirven para medir nada.** Están redactados por la
misma lógica que construyó el extractor, así que medir contra ellos solo
confirma que el código corre.

Un set que sirva cumple tres condiciones:

1. **Textos reales** que tú consumes: los mensajes, artículos y publicaciones
   que de verdad te llegan.
2. **50-100 documentos**, no ocho.
3. **Anotados por ti**, incluyendo los cuatro casos difíciles del plan:
   ciertas que suenan falsas, falsas que suenan creíbles, engañosas pero
   técnicamente ciertas, y sin evidencia pública disponible.

Sustituye estos casos por los tuyos antes de tomarte en serio cualquier
número que imprima `evidencia evaluar`.

## Nota sobre la Fase 3

Este set no mide veracidad — mide extracción. El set de veracidad (afirmación
etiquetada como apoyada / contradicha / sin evidencia suficiente) es un archivo
distinto y llega con la Fase 3.
