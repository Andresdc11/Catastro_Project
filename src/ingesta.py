# -*- coding: utf-8 -*-
"""Descarga las capas de Catastro Bogota y las guarda en data/raw/.

Es el primer paso del proyecto: lo que baja aqui lo leen tabla.py y los notebooks.
El servicio es ArcGIS REST y entrega cada capa por paginas, asi que para cada una:

    1. pregunta cuantos registros tiene;
    2. los pide de PAGINA en PAGINA, ordenados por OBJECTID;
    3. comprueba que llegaron todos;
    4. normaliza las columnas y escribe el archivo.

Solo se reemplaza un archivo cuando la descarga termino bien: un corte a mitad de
camino no deja un archivo incompleto ni borra el anterior.

Las capas ya descargadas no se tocan salvo con --forzar. El servicio publica el dato
vigente, de modo que volver a bajar puede cambiar los resultados de los notebooks.

Las construcciones no se bajan por defecto: son la capa mas lenta y los resultados
publicados usan una version anterior, guardada en data/referencia/ (ver morfologia.py).

uso:
    python src/ingesta.py                    baja las capas que falten
    python src/ingesta.py --vigente          lo mismo, y ademas las construcciones actuales
    python src/ingesta.py --listar           muestra el catalogo y que hay en disco
    python src/ingesta.py suelo precios      baja solo esas capas
    python src/ingesta.py --forzar           vuelve a bajar todo el proyecto
    python src/ingesta.py --destino CARPETA  guarda en otra carpeta, sin tocar data/raw
"""
import argparse
import http.client
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import geopandas as gpd
import pandas as pd

import config as C

BASE = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"
PAGINA = 2000                    # maxRecordCount del servicio
CRS = "EPSG:4326"                # lon/lat: tabla.py reproyecta cuando necesita metros
INTENTOS = 4
TIMEOUT_S = 180

# el servicio entrega las localidades sin tildes
TILDES = {"Usaquen": "Usaquén", "Engativa": "Engativá", "Fontibon": "Fontibón",
          "San Cristobal": "San Cristóbal", "Ciudad Bolivar": "Ciudad Bolívar",
          "Los Martires": "Los Mártires"}


# --- ajustes propios de cada capa -------------------------------------------
def _ajustar_sectores(d):
    "Un nombre por sector, en formato de titulo. Suele ser el del barrio."
    d = d.rename(columns={"SCACODIGO": "sector", "SCANOMBRE": "nombre_sector"})
    d = d.drop_duplicates("sector").copy()
    d["nombre_sector"] = d["nombre_sector"].str.strip().str.title()
    return d


def _ajustar_construcciones(d):
    "Mismo nombre de columna que en el GeoJSON historico; el area sigue en grados^2."
    return d.rename(columns={"SHAPE.AREA": "SHAPE_Area"})


def _ajustar_localidades(d):
    "Nombres de localidad con sus tildes."
    d = d.rename(columns={"LOCNOMBRE": "localidad", "LOCCODIGO": "cod_localidad"})
    d["localidad"] = d["localidad"].str.strip().str.title().replace(TILDES)
    return d


# --- catalogo: que se baja y de donde ---------------------------------------
@dataclass(frozen=True)
class Capa:
    descripcion: str
    servicio: str                # ruta del MapServer dentro de BASE
    id_capa: int                 # numero de la capa dentro del MapServer
    archivo: Path
    geometria: bool = True       # False: solo atributos, sin poligonos
    campos: str = "*"
    anio: Optional[int] = None   # None: todos los registros de la capa
    ajustar: Optional[Callable] = None
    del_proyecto: bool = True    # False: solo se baja si se pide


CATALOGO = {
    "suelo": Capa("Clases de suelo del POT; define el perimetro urbano",
                  "ordenamientoterritorial/suelo", 0, C.SUELO),
    "estratos": Capa("Estrato socioeconomico por manzana",
                     "ordenamientoterritorial/estratificacion", 1, C.ESTRATOS),
    "precios": Capa("Valor de referencia y geometria de la manzana, ano de corte",
                    "catastro/valorreferencia", 0, C.PRECIOS, anio=C.ANIO),
    "precios_serie": Capa("Valor de referencia de todos los anos, sin geometria",
                          "catastro/valorreferencia", 0, C.SERIE, geometria=False),
    "usos": Capa("Uso economico predominante, ano de corte",
                 "catastro/usopredominante", 0, C.USOS, anio=C.ANIO),
    "sectores": Capa("Nombre de cada sector catastral",
                     "catastro/sectorcatastral", 0, C.SECTORES, geometria=False,
                     campos="SCACODIGO,SCANOMBRE", ajustar=_ajustar_sectores),
    "localidades": Capa("Poligonos de las 20 localidades",
                        "ordenamientoterritorial/localidad", 0, C.LOCALIDADES,
                        campos="LOCNOMBRE,LOCCODIGO", ajustar=_ajustar_localidades),
    "construcciones": Capa("Construcciones actuales; tarda unos 35 min (ver --vigente)",
                           "catastro/construccion", 0, C.CONSTRUCCIONES, geometria=False,
                           campos="LOTECODIGO,CONCODIGO,CONNPISOS,CONTSEMIS,CONNSOTANO,SHAPE.AREA",
                           ajustar=_ajustar_construcciones, del_proyecto=False),
    "avaluos": Capa("Avaluos catastrales; ningun paso del proyecto los usa",
                    "catastro/avaluoscatastrales", 1, C.RAW / "avaluos_catastrales.gpkg",
                    del_proyecto=False),
}


# --- conversacion con el servicio -------------------------------------------
def pedir(capa, params):
    "Una consulta al servicio. Reintenta porque devuelve errores 500 a ratos."
    url = "%s/%s/MapServer/%d/query?%s" % (BASE, capa.servicio, capa.id_capa,
                                           urllib.parse.urlencode(params))
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for intento in range(1, INTENTOS + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as r:
                respuesta = json.loads(r.read().decode("utf-8", "replace"))
            if "error" in respuesta:
                raise RuntimeError(respuesta["error"].get("message", "error del servicio"))
            return respuesta
        except (OSError, http.client.HTTPException, ValueError, RuntimeError) as e:
            if intento == INTENTOS:
                raise RuntimeError("%s, capa %d: %s" % (capa.servicio, capa.id_capa, e)) from e
            time.sleep(2 * intento)


def _filtro(capa):
    "ANO es una fecha en el servicio, por eso el filtro compara contra un timestamp."
    return "1=1" if capa.anio is None else "ANO = timestamp '%d-01-01 00:00:00'" % capa.anio


def contar(capa):
    return pedir(capa, {"f": "json", "where": _filtro(capa), "returnCountOnly": "true"})["count"]


def _lote_a_tabla(capa, lote):
    if capa.geometria:
        return gpd.GeoDataFrame.from_features(lote, crs=CRS)
    return pd.DataFrame([f["attributes"] for f in lote])


def bajar_tabla(nombre, capa):
    "Pide todas las paginas de la capa. Falla si no llegan todos los registros."
    total = contar(capa)
    consulta = {"where": _filtro(capa), "outFields": capa.campos, "outSR": "4326",
                "f": "geojson" if capa.geometria else "json",
                "returnGeometry": str(capa.geometria).lower(),
                "orderByFields": "OBJECTID", "resultRecordCount": PAGINA}

    partes, recibidos, inicio = [], 0, time.time()
    while recibidos < total:
        lote = pedir(capa, dict(consulta, resultOffset=recibidos)).get("features", [])
        if not lote:
            break
        partes.append(_lote_a_tabla(capa, lote))
        recibidos += len(lote)
        print("\r   %-14s %7d / %d  (%3.0f s)" % (nombre, recibidos, total, time.time() - inicio),
              end="", flush=True)
    print()

    if total == 0 or recibidos != total:
        raise RuntimeError("%s: llegaron %d de %d registros" % (nombre, recibidos, total))
    tabla = pd.concat(partes, ignore_index=True)
    return gpd.GeoDataFrame(tabla, geometry="geometry", crs=CRS) if capa.geometria else tabla


# --- limpieza y escritura ---------------------------------------------------
def normalizar(d):
    "ANO llega como milisegundos desde 1970; los codigos deben ser texto (ceros a la izquierda)."
    if "ANO" in d.columns:
        d["ANO"] = pd.to_datetime(d["ANO"], unit="ms", errors="coerce").dt.year
    for columna in ("MANCODIGO", "CODIGO_MANZANA"):
        if columna in d.columns:
            d[columna] = d[columna].astype(str)
    return d


def escribir(d, ruta):
    "Escribe en un temporal y lo renombra al final, para no dejar archivos a medias."
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name("_tmp_" + ruta.name)
    try:
        if ruta.suffix == ".gpkg":
            temporal.unlink(missing_ok=True)      # GPKG agregaria a un archivo existente
            d.to_file(temporal, driver="GPKG", layer=ruta.stem)
        else:
            pd.DataFrame(d).to_csv(temporal, index=False)
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def descargar(nombre, destino=None, forzar=False):
    "Baja una capa del catalogo. Devuelve la ruta, o None si ya estaba y no se forzo."
    capa = CATALOGO[nombre]
    ruta = Path(destino) / capa.archivo.name if destino else capa.archivo
    if ruta.exists() and not forzar:
        print("   %-14s ya esta (--forzar para reemplazarla)" % nombre)
        return None

    tabla = normalizar(bajar_tabla(nombre, capa))
    if capa.ajustar:
        tabla = capa.ajustar(tabla)
    escribir(tabla, ruta)
    print("   %-14s %d filas -> %s (%.1f MB)" % (nombre, len(tabla), ruta, ruta.stat().st_size / 1e6))
    return ruta


def listar():
    "El catalogo y lo que ya esta en disco."
    for nombre, capa in CATALOGO.items():
        if capa.archivo.exists():
            estado = "%7.1f MB" % (capa.archivo.stat().st_size / 1e6)
        else:
            estado = "    falta" if capa.del_proyecto else " opcional"
        print("%-14s %s  %-32s %s" % (nombre, estado, capa.archivo.name, capa.descripcion))


def main(argumentos=None):
    p = argparse.ArgumentParser(description="Descarga las capas de Catastro a data/raw/.")
    p.add_argument("capas", nargs="*", metavar="capa",
                   help="capas a bajar; sin nombres, todas las del proyecto (ver --listar)")
    p.add_argument("--vigente", action="store_true", help="incluye las construcciones actuales")
    p.add_argument("--forzar", action="store_true", help="reemplaza las capas ya descargadas")
    p.add_argument("--listar", action="store_true", help="muestra el catalogo y no descarga nada")
    p.add_argument("--destino", help="carpeta de salida en lugar de data/raw")
    a = p.parse_args(argumentos)

    desconocidas = [n for n in a.capas if n not in CATALOGO]
    if desconocidas:
        p.error("capas desconocidas: %s. Opciones: %s" % (", ".join(desconocidas), ", ".join(CATALOGO)))
    if a.listar:
        listar()
        return
    nombres = a.capas or [n for n, capa in CATALOGO.items() if capa.del_proyecto]
    if a.vigente and "construcciones" not in nombres:
        nombres = nombres + ["construcciones"]
    for nombre in nombres:
        descargar(nombre, destino=a.destino, forzar=a.forzar)


if __name__ == "__main__":
    main()
