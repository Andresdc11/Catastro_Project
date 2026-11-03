# -*- coding: utf-8 -*-
"""Resume las construcciones de Catastro en una fila por manzana.

Son unos 2.4 millones de registros, asi que se recorren uno a uno sin cargarlos todos.
El area ya viene en SHAPE_Area (grados^2) y no hace falta procesar la geometria.

Por defecto se reproducen los resultados publicados:
    - si existe config.GEOJSON, la copia historica de las construcciones, se calcula con ella;
    - si no, se copia config.MORFOLOGIA_REFERENCIA, el resultado guardado de ese calculo.

Con --vigente se calcula con la version actual del servicio (config.CONSTRUCCIONES), que
baja `python src/ingesta.py --vigente`. Algunos resultados cambian: ver el README.

Codigo catastral del lote (LOTECODIGO, 12 digitos): SSSSSS MMM LLL
    sector | manzana | lote.  La manzana son los primeros 9 digitos.

Se descartan las construcciones sin un codigo valido y aquellas con un area fuera de
[MIN_AREA_M2, MAX_AREA_M2] (ver config.py). Los pisos se limitan al rango [1, MAX_PISOS].

Con h = huella de cada construccion en m2 y p = sus pisos, por manzana:

    n_construcciones     numero de construcciones
    n_lotes              lotes distintos
    area_huella_m2       suma de h
    area_construida_m2   suma de h * p
    pisos_prom_pond      area_construida_m2 / area_huella_m2 (promedio ponderado por area)
    pisos_max            maximo de p
    frac_pisos_ge3       fraccion de construcciones con p >= 3
    frac_subterraneo     fraccion con sotano o semisotano
    huella_media_m2      area_huella_m2 / n_construcciones

uso:
    python src/morfologia.py              reproduce los resultados publicados
    python src/morfologia.py --vigente    usa la version actual del servicio
"""
import argparse
import csv
import gzip
import json
import shutil
import time
from collections import defaultdict

import pandas as pd

import config as C

M2_POR_GRADO2 = (C.KM_POR_GRADO_LON * 1000) * (C.KM_POR_GRADO_LAT * 1000)
AVISO_CADA = 500_000             # registros entre un mensaje de avance y el siguiente
CAMPOS_NUMERICOS = ("CONNPISOS", "CONNSOTANO", "CONTSEMIS", "SHAPE_Area")


def leer_geojson(ruta):
    "Las propiedades de cada construccion. El GeoJSON trae una por linea."
    with open(ruta, encoding="utf-8", buffering=1 << 20) as archivo:
        for linea in archivo:
            if linea.startswith('{ "type": "Feature"'):
                inicio = linea.index('"properties": ') + len('"properties": ')
                yield json.loads(linea[inicio:linea.index(', "geometry"', inicio)])


def leer_csv(ruta):
    "Lo mismo desde el CSV de ingesta.py, donde todo llega como texto y lo vacio es ''."
    with gzip.open(ruta, "rt", encoding="utf-8", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            for campo in CAMPOS_NUMERICOS:
                fila[campo] = float(fila[campo]) if fila[campo] else None
            yield fila


def _codigo_lote(p):
    "Los 12 digitos del lote, o None si no hay un codigo valido."
    codigo = p.get("LOTECODIGO") or (p.get("CONCODIGO") or "")[:12]
    return codigo if len(codigo) >= 12 and codigo.isdigit() else None


def _manzana_vacia():
    return {"n": 0, "lotes": set(), "huella": 0.0, "construida": 0.0,
            "pisos_max": 0, "ge3": 0, "sub": 0}


def _sumar(manzana, lote, area, pisos, bajo_tierra):
    "Acumula una construccion en los totales de su manzana."
    manzana["n"] += 1
    manzana["lotes"].add(lote)
    manzana["huella"] += area
    manzana["construida"] += area * pisos
    manzana["pisos_max"] = max(manzana["pisos_max"], pisos)
    manzana["ge3"] += pisos >= 3
    manzana["sub"] += bajo_tierra


def acumular(registros):
    "Recorre las construcciones y devuelve los totales acumulados de cada manzana."
    manzanas = defaultdict(_manzana_vacia)
    descartes = {"codigo": 0, "area": 0}
    inicio = time.time()

    for n, p in enumerate(registros, start=1):
        if n % AVISO_CADA == 0:
            print("  %9d registros  (%.0f s)" % (n, time.time() - inicio), flush=True)

        codigo = _codigo_lote(p)
        if codigo is None:
            descartes["codigo"] += 1
            continue
        area = (p.get("SHAPE_Area") or 0) * M2_POR_GRADO2
        if not C.MIN_AREA_M2 <= area <= C.MAX_AREA_M2:
            descartes["area"] += 1
            continue

        pisos = min(max(int(p.get("CONNPISOS") or 0), 1), C.MAX_PISOS)
        bajo_tierra = (p.get("CONNSOTANO") or 0) > 0 or (p.get("CONTSEMIS") or 0) > 0
        _sumar(manzanas[codigo[:9]], codigo[9:], area, pisos, bajo_tierra)

    print("  %d manzanas en %.0f s | descartes: %s"
          % (len(manzanas), time.time() - inicio, descartes))
    return manzanas


def a_tabla(manzanas):
    "Convierte los totales en las columnas descritas al inicio del archivo."
    return pd.DataFrame([{
        "MANCODIGO": codigo,
        "n_construcciones": m["n"],
        "n_lotes": len(m["lotes"]),
        "area_huella_m2": round(m["huella"], 1),
        "area_construida_m2": round(m["construida"], 1),
        "pisos_prom_pond": round(m["construida"] / m["huella"], 3),
        "pisos_max": m["pisos_max"],
        "frac_pisos_ge3": round(m["ge3"] / m["n"], 4),
        "frac_subterraneo": round(m["sub"] / m["n"], 4),
        "huella_media_m2": round(m["huella"] / m["n"], 1),
    } for codigo, m in manzanas.items()])


def _guardar(tabla):
    tabla.to_csv(C.MORFOLOGIA, index=False)
    print("escrito %s: %d manzanas" % (C.MORFOLOGIA.name, len(tabla)))


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Resume las construcciones por manzana.")
    parser.add_argument("--vigente", action="store_true",
                        help="usa la version actual del servicio en lugar de la publicada")
    vigente = parser.parse_args(argumentos).vigente
    C.PROC.mkdir(parents=True, exist_ok=True)

    if vigente:
        if not C.CONSTRUCCIONES.exists():
            raise SystemExit("Faltan las construcciones. Corre antes: python src/ingesta.py --vigente")
        print("leyendo %s, version vigente del servicio" % C.CONSTRUCCIONES.name)
        _guardar(a_tabla(acumular(leer_csv(C.CONSTRUCCIONES))))
    elif C.GEOJSON.exists():
        print("leyendo %s, copia historica (%.1f GB)" % (C.GEOJSON.name, C.GEOJSON.stat().st_size / 1e9))
        _guardar(a_tabla(acumular(leer_geojson(C.GEOJSON))))
    else:
        shutil.copyfile(C.MORFOLOGIA_REFERENCIA, C.MORFOLOGIA)
        print("copiada la morfologia de referencia a %s" % C.MORFOLOGIA.name)


if __name__ == "__main__":
    main()
