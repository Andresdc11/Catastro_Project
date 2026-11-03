# -*- coding: utf-8 -*-
"""Actualiza solo los nombres para ubicar zonas: sectores catastrales y localidades.

Los usan los notebooks 01 y 03 para decir en que barrio y localidad cae cada manzana.
La descarga esta en ingesta.py; este atajo siempre reemplaza los dos archivos.

uso:  python src/zonas.py
"""
from ingesta import main

if __name__ == "__main__":
    main(["sectores", "localidades", "--forzar"])
