# -*- coding: utf-8 -*-
"""Arma la tabla del proyecto: una fila por manzana urbana con precio.

De donde sale cada grupo de columnas:

    Fuente                 Cruce                 Columnas
    valor de referencia    base de la tabla      cop_m2, sector, geometria
    suelo POT              espacial              filtro: solo urbano y expansion
    uso predominante       MANCODIGO             uso
    estratos               espacial (*)          estrato
    morfologia.py          MANCODIGO             construcciones, lotes, pisos, huella
    (calculadas aqui)                            ver abajo

    (*) el codigo de manzana de la capa de estratos no es MANCODIGO.

Variables que se calculan aqui:

    sector               primeros 6 digitos de MANCODIGO
    area_manzana_m2      area del poligono, proyectado a metros
    compacidad           4 pi area / perimetro^2; 1 es un circulo
    indice_construccion  area_construida_m2 / area_manzana_m2, con tope en el percentil 99.5
    indice_ocupacion     area_huella_m2 / area_manzana_m2, con tope en 1
    densidad_lotes_ha    n_lotes / hectareas de la manzana
    ivs                  percentil de intensidad edificatoria (ver calcular_ivs)
    lon, lat             punto representativo de la manzana
    dist_<centro>_km     distancia a cada centralidad de config.CENTROS
    dist_centro_cercano_km, centro_cercano   la menor de esas distancias y su centralidad
    dist_cerros_km       distancia al este hasta el borde oriental (ver agregar_ubicacion)
    pbdir_sin, pbdir_cos direccion desde la Plaza de Bolivar; rumbo 0 = norte
    vecinos_500m, vecinos_1km   otras manzanas dentro de ese radio
    dist_vecino_8_km     distancia a la octava manzana mas cercana

Requiere haber corrido ingesta.py y morfologia.py.

uso:  python src/tabla.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import config as C

CLASES_SUELO = [1, 2]            # SUECSUELO: 1 urbano, 2 expansion, 3 rural
CRS_METROS = 3116                # MAGNA-SIRGAS Bogota
CUANTIL_TOPE_IC = .995           # tope del indice de construccion
MIN_CONSTRUCCIONES_IVS = 5       # minimo de construcciones para calcular el IVS
BANDA_LATITUD_GRADOS = .01       # ancho de cada banda para ubicar los cerros, cerca de 1 km
CUANTIL_BORDE_CERROS = .99       # cuantil de longitud que marca el borde en cada banda
BANDAS_SUAVIZADO = 5             # bandas de la mediana movil que suaviza ese borde


def a_km(lon, lat):
    "Convierte grados a coordenadas planas en km."
    return np.c_[np.asarray(lon) * C.KM_POR_GRADO_LON, np.asarray(lat) * C.KM_POR_GRADO_LAT]


def cargar_precios():
    "Precio y geometria de cada manzana dentro del perimetro urbano, con precio positivo."
    precios = gpd.read_file(C.PRECIOS)[["MANCODIGO", "V_REF", "geometry"]]

    # unas pocas manzanas vienen partidas en varios poligonos: se unen
    partida = precios["MANCODIGO"].duplicated(keep=False)
    unidas = precios[partida].dissolve(by="MANCODIGO", aggfunc="first").reset_index()
    precios = pd.concat([precios[~partida], unidas], ignore_index=True)

    suelo = gpd.read_file(C.SUELO)
    perimetro = suelo[suelo["SUECSUELO"].isin(CLASES_SUELO)].geometry.union_all()
    dentro = precios.geometry.representative_point().within(perimetro)

    d = precios[dentro & (precios["V_REF"] > 0)].copy()
    d = d.rename(columns={"V_REF": "cop_m2"})
    d["sector"] = d["MANCODIGO"].str[:6]
    print("manzanas urbanas con precio: %d" % len(d))
    return d


def agregar_uso(d):
    usos = gpd.read_file(C.USOS, ignore_geometry=True)[["MANCODIGO", "GRUPOUSOECON"]]
    usos = usos.drop_duplicates("MANCODIGO").rename(columns={"GRUPOUSOECON": "uso"})
    return d.merge(usos, on="MANCODIGO", how="left")


def agregar_estrato(d):
    "Cada manzana toma el estrato del poligono donde cae su punto representativo."
    estratos = gpd.read_file(C.ESTRATOS)[["ESTRATO", "geometry"]].to_crs(d.crs)
    puntos = gpd.GeoDataFrame(d[["MANCODIGO"]], geometry=d.geometry.representative_point(),
                              crs=d.crs)
    cruce = gpd.sjoin(puntos, estratos, how="left", predicate="within").drop_duplicates("MANCODIGO")
    cruce = cruce[["MANCODIGO", "ESTRATO"]].rename(columns={"ESTRATO": "estrato"})
    d = d.merge(cruce, on="MANCODIGO", how="left")
    d.loc[d["estrato"] == 0, "estrato"] = np.nan     # 0 es "sin estratificar", no un nivel
    return d


def agregar_morfologia(d):
    "Une lo que deja morfologia.py y lo relaciona con el area real de la manzana."
    morfologia = pd.read_csv(C.MORFOLOGIA, dtype={"MANCODIGO": str})
    d = d.merge(morfologia, on="MANCODIGO", how="left")

    en_metros = d.to_crs(CRS_METROS)
    d["area_manzana_m2"] = en_metros.area.round(1)
    d["compacidad"] = (4 * np.pi * en_metros.area / en_metros.length ** 2).round(4)

    indice_construccion = d["area_construida_m2"] / d["area_manzana_m2"]
    d["indice_construccion"] = indice_construccion.clip(upper=indice_construccion.quantile(CUANTIL_TOPE_IC))
    d["indice_ocupacion"] = (d["area_huella_m2"] / d["area_manzana_m2"]).clip(upper=1)
    d["densidad_lotes_ha"] = d["n_lotes"] / (d["area_manzana_m2"] / 1e4)
    return d


def calcular_ivs(d):
    """Indice de intensidad edificatoria (IVS) del proyecto anterior, de 0 a 100.

    1. Estandariza cinco rasgos y les aplica un PCA, solo en las manzanas con datos
       completos y al menos MIN_CONSTRUCCIONES_IVS construcciones.
    2. Retiene las componentes con varianza mayor que 1 (criterio de Kaiser).
    3. Orienta cada componente para que crezca con la huella: el signo de un PCA es arbitrario.
    4. Las promedia, ponderadas por la varianza que explican, y pasa el resultado a percentil.

    Las demas manzanas quedan sin IVS.
    """
    rasgos = pd.DataFrame({"log_ic": np.log1p(d["indice_construccion"]),
                           "pisos": d["pisos_prom_pond"],
                           "ge3": d["frac_pisos_ge3"],
                           "sub": d["frac_subterraneo"],
                           "log_huella": np.log1p(d["huella_media_m2"])})
    validas = (d["n_construcciones"] >= MIN_CONSTRUCCIONES_IVS) & rasgos.notna().all(axis=1)

    estandarizados = StandardScaler().fit_transform(rasgos[validas])
    pca = PCA(random_state=C.SEMILLA).fit(estandarizados)
    componentes = pca.transform(estandarizados)

    retenidas = max(int((pca.explained_variance_ > 1).sum()), 1)
    for j in range(retenidas):
        if np.corrcoef(componentes[:, j], rasgos.loc[validas, "log_huella"])[0, 1] < 0:
            componentes[:, j] *= -1

    varianza = pca.explained_variance_ratio_[:retenidas]
    pesos = varianza / varianza.sum()
    indice = pd.Series(componentes[:, :retenidas] @ pesos, index=d.index[validas])
    d.loc[validas, "ivs"] = indice.rank(pct=True) * 100
    print("IVS: %d componentes retenidas, %d manzanas" % (retenidas, validas.sum()))
    return d


def _distancia_a_cerros(d):
    """Distancia hacia el este hasta el borde oriental de la ciudad, en km.

    El borde se estima por bandas de latitud: el cuantil 0.99 de la longitud en cada banda,
    suavizado con una mediana movil. Es una aproximacion a partir de las propias manzanas.
    """
    banda = (d["lat"] / BANDA_LATITUD_GRADOS).round()
    borde = (d.groupby(banda)["lon"].quantile(CUANTIL_BORDE_CERROS)
             .rolling(BANDAS_SUAVIZADO, center=True, min_periods=1).median())
    return ((banda.map(borde) - d["lon"]).clip(lower=0) * C.KM_POR_GRADO_LON).round(3)


def agregar_ubicacion(d):
    "Distancias a las centralidades y a los cerros, direccion y densidad de manzanas vecinas."
    puntos = d.geometry.representative_point()
    d["lon"], d["lat"] = puntos.x.values, puntos.y.values
    xy = a_km(d["lon"], d["lat"])

    for nombre, (lon, lat) in C.CENTROS.items():
        d["dist_%s_km" % nombre] = np.hypot(*(xy - a_km(lon, lat)[0]).T).round(3)
    distancias = d[["dist_%s_km" % n for n in C.CENTROS]]
    d["dist_centro_cercano_km"] = distancias.min(axis=1)
    d["centro_cercano"] = distancias.idxmin(axis=1).str[len("dist_"):-len("_km")]

    d["dist_cerros_km"] = _distancia_a_cerros(d)

    lon_plaza, lat_plaza = C.CENTROS["centro_historico"]
    rumbo = np.arctan2((d["lon"] - lon_plaza) * C.KM_POR_GRADO_LON,
                       (d["lat"] - lat_plaza) * C.KM_POR_GRADO_LAT)
    d["pbdir_sin"], d["pbdir_cos"] = np.sin(rumbo).round(4), np.cos(rumbo).round(4)

    # cada consulta encuentra tambien a la propia manzana: por eso el -1 y el k=9
    arbol = cKDTree(xy)
    d["vecinos_500m"] = [len(v) - 1 for v in arbol.query_ball_point(xy, .5)]
    d["vecinos_1km"] = [len(v) - 1 for v in arbol.query_ball_point(xy, 1.0)]
    d["dist_vecino_8_km"] = arbol.query(xy, k=9)[0][:, 8].round(4)
    return d


def revisar_centralidades(d):
    "Las coordenadas de config.CENTROS son aproximadas: esto permite comprobarlas a ojo."
    arbol = cKDTree(a_km(d["lon"], d["lat"]))
    print("\ncentralidad            manzana mas cercana   mediana COP/m2 a 1 km")
    for nombre, (lon, lat) in C.CENTROS.items():
        distancia, _ = arbol.query(a_km(lon, lat)[0])
        cerca = d["dist_%s_km" % nombre] <= 1
        print("  %-20s %8.0f m           %12s"
              % (nombre, 1000 * distancia, format(d.loc[cerca, "cop_m2"].median(), ",.0f")))


def main():
    d = cargar_precios()
    d = agregar_uso(d)
    d = agregar_estrato(d)
    d = agregar_morfologia(d)
    d = calcular_ivs(d)
    d = agregar_ubicacion(d)
    revisar_centralidades(d)

    C.PROC.mkdir(parents=True, exist_ok=True)
    d.to_file(C.TABLA)
    print("\nescrito %s: %d manzanas x %d columnas" % (C.TABLA.name, len(d), d.shape[1]))
    print("con morfologia: %d | con estrato: %d | con uso: %d"
          % (d["n_construcciones"].notna().sum(), d["estrato"].notna().sum(), d["uso"].notna().sum()))


if __name__ == "__main__":
    main()
