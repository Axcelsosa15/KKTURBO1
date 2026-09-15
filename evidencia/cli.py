"""Interfaz de línea de comandos.

    evidencia extraer [ARCHIVO]     analiza un texto (o stdin) y emite el informe
    evidencia evaluar               mide la Fase 1 contra el set anotado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evidencia.cache import DIRECTORIO_POR_DEFECTO, ProveedorConCache
from evidencia.evaluacion import a_texto, cargar_set, evaluar
from evidencia.extraccion import MAX_CARACTERES_FRAGMENTO, extraer
from evidencia.informe import a_markdown
from evidencia.llm import MODELO_POR_DEFECTO, ErrorProveedor, ProveedorAnthropic

SET_POR_DEFECTO = Path("eval/extraccion.jsonl")


def _construir_proveedor(args):
    proveedor = ProveedorAnthropic(
        modelo=args.modelo, effort=args.effort, max_tokens=args.max_tokens
    )
    if args.sin_cache:
        return proveedor
    return ProveedorConCache(proveedor, args.directorio_cache)


def _leer_entrada(ruta: str | None) -> str:
    if ruta is None or ruta == "-":
        if sys.stdin.isatty():
            raise SystemExit(
                "No hay texto que analizar. Pasa un archivo o canaliza texto por stdin."
            )
        return sys.stdin.read()
    return Path(ruta).read_text(encoding="utf-8")


def _comando_extraer(args) -> int:
    texto = _leer_entrada(args.archivo)
    if not texto.strip():
        raise SystemExit("El texto de entrada está vacío.")

    resultado = extraer(texto, _construir_proveedor(args), args.max_caracteres)

    if args.formato == "json":
        print(resultado.model_dump_json(indent=2))
    else:
        print(a_markdown(resultado), end="")
    return 0


def _comando_evaluar(args) -> int:
    ruta = Path(args.set)
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}. Es el set anotado a mano de la Fase 0: sin él no hay "
            "forma de saber si un cambio mejora o empeora la extracción."
        )

    casos = cargar_set(ruta)
    if not casos:
        raise SystemExit(f"{ruta} no contiene ningún caso.")

    resultados = evaluar(casos, _construir_proveedor(args))
    print(a_texto(resultados))
    return 0 if resultados.aprueba else 1


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidencia",
        description=(
            "Extrae las afirmaciones verificables de un texto y las ancla a su cita "
            "literal. No decide si son ciertas."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def comunes(p):
        p.add_argument("--modelo", default=MODELO_POR_DEFECTO)
        p.add_argument(
            "--effort",
            choices=["low", "medium", "high", "xhigh", "max"],
            default=None,
            help="Profundidad de razonamiento. Si se omite, se usa la del modelo.",
        )
        p.add_argument("--max-tokens", type=int, default=16000)
        p.add_argument(
            "--sin-cache",
            action="store_true",
            help="Ignora la caché y vuelve a llamar al modelo (cuesta dinero).",
        )
        p.add_argument("--directorio-cache", default=str(DIRECTORIO_POR_DEFECTO))

    p_extraer = sub.add_parser("extraer", help="Analiza un texto.")
    p_extraer.add_argument("archivo", nargs="?", help="Ruta al texto; '-' o vacío lee stdin.")
    p_extraer.add_argument("--formato", choices=["md", "json"], default="md")
    p_extraer.add_argument(
        "--max-caracteres",
        type=int,
        default=MAX_CARACTERES_FRAGMENTO,
        help="Tamaño máximo de cada fragmento enviado al modelo.",
    )
    comunes(p_extraer)
    p_extraer.set_defaults(func=_comando_extraer)

    p_evaluar = sub.add_parser("evaluar", help="Mide la Fase 1 contra el set anotado.")
    p_evaluar.add_argument("--set", default=str(SET_POR_DEFECTO))
    comunes(p_evaluar)
    p_evaluar.set_defaults(func=_comando_evaluar)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.func(args)
    except ErrorProveedor as error:
        print(f"Error del proveedor: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
