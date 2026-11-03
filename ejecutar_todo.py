# -*- coding: utf-8 -*-
"""Ejecuta todo el proyecto, en orden, desde la descarga hasta los informes.

Se detiene en el primer paso que falle. Para retomar desde ahi, usa --desde.
Los notebooks se ejecutan y se guardan en su lugar, con sus salidas actualizadas.

uso:
    python ejecutar_todo.py                  todos los pasos, con la morfologia publicada
    python ejecutar_todo.py --vigente        con las construcciones actuales de Catastro
    python ejecutar_todo.py --listar         muestra los pasos, sin ejecutar nada
    python ejecutar_todo.py --desde 02       retoma desde ese paso
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parent
LIMITE_CELDA_S = 3600
SRC = RAIZ / "src"
POTENCIAL = RAIZ / "potencial_manzanas"

# (nombre, archivo, carpeta de trabajo). El orden importa: cada paso usa lo que deja el anterior.
PASOS = [
    ("ingesta", SRC / "ingesta.py", RAIZ),
    ("morfologia", SRC / "morfologia.py", RAIZ),
    ("tabla", SRC / "tabla.py", RAIZ),
    ("01", RAIZ / "notebooks" / "01_valor_suelo.ipynb", RAIZ / "notebooks"),
    ("02", RAIZ / "notebooks" / "02_pronostico.ipynb", RAIZ / "notebooks"),
    ("03", RAIZ / "notebooks" / "03_clusters.ipynb", RAIZ / "notebooks"),
    ("potencial", POTENCIAL / "run.py", POTENCIAL),
    ("informe", POTENCIAL / "informe_potencial.ipynb", POTENCIAL),
]
PASOS_CON_VIGENTE = ("ingesta", "morfologia")


def correr_script(script, carpeta, argumentos=()):
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(script), *argumentos], cwd=carpeta, env=entorno, check=True)


def correr_notebook(ruta, carpeta):
    "Usa el kernel 'python3' del entorno activo, sea cual sea el que el notebook tenga guardado."
    notebook = nbformat.read(ruta, as_version=4)
    cliente = NotebookClient(notebook, timeout=LIMITE_CELDA_S, kernel_name="python3",
                             resources={"metadata": {"path": str(carpeta)}})
    cliente.execute()
    nbformat.write(notebook, ruta)


def main():
    nombres = [p[0] for p in PASOS]
    parser = argparse.ArgumentParser(description="Ejecuta todo el proyecto en orden.")
    parser.add_argument("--desde", choices=nombres, default=nombres[0], help="paso desde el que empezar")
    parser.add_argument("--listar", action="store_true", help="muestra los pasos y termina")
    parser.add_argument("--vigente", action="store_true",
                        help="usa las construcciones actuales de Catastro, no las publicadas")
    args = parser.parse_args()

    if args.listar:
        for nombre, archivo, _ in PASOS:
            print("%-11s %s" % (nombre, archivo.relative_to(RAIZ)))
        return

    os.environ["PYTHONIOENCODING"] = "utf-8"
    inicio_total = time.time()
    for nombre, archivo, carpeta in PASOS[nombres.index(args.desde):]:
        print("\n=== %s: %s" % (nombre, archivo.relative_to(RAIZ)), flush=True)
        inicio = time.time()
        if archivo.suffix == ".ipynb":
            correr_notebook(archivo, carpeta)
        elif args.vigente and nombre in PASOS_CON_VIGENTE:
            correr_script(archivo, carpeta, ["--vigente"])
        else:
            correr_script(archivo, carpeta)
        print("=== %s listo en %.1f min" % (nombre, (time.time() - inicio) / 60), flush=True)
    print("\nTodo listo en %.1f min" % ((time.time() - inicio_total) / 60))


if __name__ == "__main__":
    main()
