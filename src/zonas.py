# -*- coding: utf-8 -*-
"""Nombres para ubicar zonas: sector catastral y localidad.

Fuentes (Catastro Bogota, ArcGIS REST):
    catastro/sectorcatastral          codigo y nombre del sector, sin geometria
    ordenamientoterritorial/localidad poligonos de las localidades

Las usa el notebook 03 para decir en que barrio y localidad cae cada atipica.

uso:  python src/zonas.py
"""
import json
import time
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd

import config as C

BASE = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"
PAGINA = 2000                    # maxRecordCount del servicio

# el servicio entrega las localidades sin tildes
TILDES = {"Usaquen": "Usaquén", "Engativa": "Engativá",
          "Fontibon": "Fontibón", "San Cristobal": "San Cristóbal", "Ciudad Bolivar": "Ciudad Bolívar",
          "Los Martires": "Los Mártires"}


def pedir(servicio, params, intentos=4):
    "reintentos porque el servicio devuelve 500 a ratos."
    url = "%s/%s/MapServer/0/query?%s" % (BASE, servicio, urllib.parse.urlencode(params))
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode("utf-8"))
            if "error" in d:
                raise RuntimeError(d["error"].get("message", "error del servicio"))
            return d
        except Exception as e:
            if i == intentos - 1:
                raise RuntimeError("%s: %s" % (servicio, e))
            time.sleep(2 * (i + 1))


def bajar(servicio, campos, geometria):
    base = {"where": "1=1", "outFields": campos, "outSR": "4326", "orderByFields": "OBJECTID",
            "f": "geojson" if geometria else "json", "returnGeometry": str(geometria).lower(),
            "resultRecordCount": PAGINA}
    partes, off = [], 0
    while True:
        lote = pedir(servicio, dict(base, resultOffset=off))["features"]
        partes += lote
        off += len(lote)
        if len(lote) < PAGINA:
            break
    if geometria:
        return gpd.GeoDataFrame.from_features(partes, crs="EPSG:4326")
    return pd.DataFrame([f["attributes"] for f in partes])


sectores = (bajar("catastro/sectorcatastral", "SCACODIGO,SCANOMBRE", False)
            .rename(columns={"SCACODIGO": "sector", "SCANOMBRE": "nombre_sector"})
            .drop_duplicates("sector"))
sectores["nombre_sector"] = sectores["nombre_sector"].str.strip().str.title()
sectores.to_csv(C.SECTORES, index=False)
print("sectores catastrales: %d -> %s" % (len(sectores), C.SECTORES.name))

loc = (bajar("ordenamientoterritorial/localidad", "LOCNOMBRE,LOCCODIGO", True)
       .rename(columns={"LOCNOMBRE": "localidad", "LOCCODIGO": "cod_localidad"}))
loc["localidad"] = loc["localidad"].str.strip().str.title().replace(TILDES)
loc.to_file(C.LOCALIDADES, driver="GPKG", layer="localidades")
print("localidades: %d -> %s" % (len(loc), C.LOCALIDADES.name))
