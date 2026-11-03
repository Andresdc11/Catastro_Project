# -*- coding: utf-8 -*-
"""Rutas y parametros del proyecto."""
from math import cos, radians
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"

# construcciones: morfologia.py explica cuando se usa cada una
GEOJSON = RAIZ.parent / "Catastro_ML" / "Construcciones.geojson"     # copia historica, opcional
MORFOLOGIA_REFERENCIA = RAIZ / "data" / "referencia" / "morfologia_manzanas.csv.gz"
CONSTRUCCIONES = RAW / "construcciones.csv.gz"                       # version vigente

ANIO = 2026
ANIO_INI = 2017
SEMILLA = 42

# de grados a kilometros, a la latitud de Bogota (4.65 N)
KM_POR_GRADO_LON = 111.320 * cos(radians(4.65))
KM_POR_GRADO_LAT = 110.574

# capas de Catastro: las baja ingesta.py
SUELO = RAW / "suelo_pot.gpkg"
ESTRATOS = RAW / "estratos_manzana.gpkg"
PRECIOS = RAW / ("valor_referencia_%d.gpkg" % ANIO)
SERIE = RAW / "valor_referencia_serie.csv.gz"
USOS = RAW / ("uso_predominante_%d.gpkg" % ANIO)
SECTORES = RAW / "sectores_catastrales.csv"     # nombre de cada sector
LOCALIDADES = RAW / "localidades.gpkg"

# lo que produce el pipeline
MORFOLOGIA = PROC / "morfologia_manzanas.csv.gz"
TABLA = PROC / "manzanas.gpkg"

# filtros de la ingesta
MIN_AREA_M2 = 1.0           # por debajo es un sliver de digitalizacion
MAX_AREA_M2 = 200_000.0     # por encima, error de digitalizacion
MAX_PISOS = 60

# centralidades (lon, lat). Coordenadas aproximadas: el pipeline imprime a que
# distancia queda la manzana mas cercana de cada una para revisarlas.
CENTROS = {
    "centro_historico": (-74.0761, 4.5981),     # Plaza de Bolivar
    "centro_internacional": (-74.0706, 4.6105), # Cra 7 con Cl 26
    "zona_t": (-74.0527, 4.6668),               # Cl 82 con Cra 12, Andino
    "calle_100": (-74.0530, 4.6860),            # Cl 100 con Cra 15
    "usaquen": (-74.0306, 4.6950),              # parque fundacional
    "salitre": (-74.1040, 4.6530),              # Av La Esperanza con Av 68
    "aeropuerto": (-74.1469, 4.7016),           # El Dorado
    "centro_sur": (-74.1600, 4.5900),           # Kennedy - Bosa
}
