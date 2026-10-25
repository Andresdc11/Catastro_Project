# -*- coding: utf-8 -*-
"""Morfologia por manzana a partir de Construcciones.geojson.

El archivo tiene 2.4 millones de construcciones, una por linea, y no cabe en
memoria. Se recorre linea a linea leyendo solo el bloque de propiedades: el area
ya viene en SHAPE_Area (grados^2) y basta convertirla a m2, asi que no hace falta
parsear la geometria.

Codigo catastral del lote (LOTECODIGO, 12 digitos): SSSSSS MMM LLL
    sector | manzana | lote.  La manzana son los primeros 9.

uso:  python src/morfologia.py
"""
import json
import time
from collections import defaultdict
from math import cos, radians

import pandas as pd

import config as C

M2_POR_GRADO2 = 111_320.0 * cos(radians(4.65)) * 110_574.0   # a la latitud de Bogota


def leer(ruta):
    mz = defaultdict(lambda: {"n": 0, "lotes": set(), "huella": 0.0, "construida": 0.0,
                              "pisos_max": 0, "ge3": 0, "sub": 0})
    descartes = {"codigo": 0, "area": 0}
    t0 = time.time()

    with open(ruta, encoding="utf-8", buffering=1 << 20) as fh:
        for n, linea in enumerate(fh):
            if not linea.startswith('{ "type": "Feature"'):
                continue
            i = linea.index('"properties": ') + 14
            p = json.loads(linea[i:linea.index(', "geometry"', i)])

            codigo = p.get("LOTECODIGO") or (p.get("CONCODIGO") or "")[:12]
            if len(codigo) < 12 or not codigo.isdigit():
                descartes["codigo"] += 1
                continue
            area = (p.get("SHAPE_Area") or 0) * M2_POR_GRADO2
            if not C.MIN_AREA_M2 <= area <= C.MAX_AREA_M2:
                descartes["area"] += 1
                continue

            pisos = min(max(int(p.get("CONNPISOS") or 0), 1), C.MAX_PISOS)
            bajo_tierra = (p.get("CONNSOTANO") or 0) > 0 or (p.get("CONTSEMIS") or 0) > 0

            m = mz[codigo[:9]]
            m["n"] += 1
            m["lotes"].add(codigo[9:])
            m["huella"] += area
            m["construida"] += area * pisos
            m["pisos_max"] = max(m["pisos_max"], pisos)
            m["ge3"] += pisos >= 3
            m["sub"] += bajo_tierra

            if n % 500_000 == 0 and n:
                print("  %9d lineas  (%.0f s)" % (n, time.time() - t0), flush=True)

    print("  %d manzanas en %.0f s | descartes: %s" % (len(mz), time.time() - t0, descartes))
    return mz


def a_tabla(mz):
    filas = []
    for codigo, m in mz.items():
        filas.append({
            "MANCODIGO": codigo,
            "n_construcciones": m["n"],
            "n_lotes": len(m["lotes"]),
            "area_huella_m2": round(m["huella"], 1),
            "area_construida_m2": round(m["construida"], 1),
            "pisos_prom_pond": round(m["construida"] / m["huella"], 3),   # ponderado por area
            "pisos_max": m["pisos_max"],
            "frac_pisos_ge3": round(m["ge3"] / m["n"], 4),
            "frac_subterraneo": round(m["sub"] / m["n"], 4),
            "huella_media_m2": round(m["huella"] / m["n"], 1),
        })
    return pd.DataFrame(filas)


if __name__ == "__main__":
    print("leyendo %s (%.1f GB)" % (C.GEOJSON.name, C.GEOJSON.stat().st_size / 1e9))
    t = a_tabla(leer(C.GEOJSON))
    C.PROC.mkdir(parents=True, exist_ok=True)
    t.to_csv(C.MORFOLOGIA, index=False)
    print("escrito %s: %d manzanas" % (C.MORFOLOGIA.name, len(t)))
