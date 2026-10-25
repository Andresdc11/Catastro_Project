# -*- coding: utf-8 -*-
"""Una fila por manzana con todo lo que usan los notebooks.

Fuentes:
    valor de referencia 2026   precio del suelo y geometria de la manzana
    morfologia                 lo que produce morfologia.py
    uso predominante 2026      cruza por MANCODIGO
    estratos                   cruce espacial: su codigo de manzana no es MANCODIGO
    suelo POT                  para quedarse con el perimetro urbano

uso:  python src/tabla.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import config as C

KM_LON = 111.320 * np.cos(np.radians(4.65))     # km por grado a la latitud de Bogota
KM_LAT = 110.574


def km(lon, lat):
    return np.c_[np.asarray(lon) * KM_LON, np.asarray(lat) * KM_LAT]


# --- precio y geometria ----------------------------------------------------
pr = gpd.read_file(C.PRECIOS)[["MANCODIGO", "V_REF", "geometry"]]

# unas pocas manzanas vienen partidas en varios poligonos: se unen
rep = pr["MANCODIGO"].duplicated(keep=False)
pr = pd.concat([pr[~rep], pr[rep].dissolve(by="MANCODIGO", aggfunc="first").reset_index()],
               ignore_index=True)

suelo = gpd.read_file(C.SUELO)
urbano = suelo[suelo["SUECSUELO"].isin([1, 2])].geometry.union_all()   # urbano + expansion
punto = pr.geometry.representative_point()
d = pr[punto.within(urbano) & (pr["V_REF"] > 0)].copy()
d = d.rename(columns={"V_REF": "cop_m2"})
d["sector"] = d["MANCODIGO"].str[:6]
print("manzanas urbanas con precio: %d" % len(d))

# --- uso y estrato ---------------------------------------------------------
usos = gpd.read_file(C.USOS, ignore_geometry=True)[["MANCODIGO", "GRUPOUSOECON"]]
d = d.merge(usos.drop_duplicates("MANCODIGO").rename(columns={"GRUPOUSOECON": "uso"}),
            on="MANCODIGO", how="left")

punto = d.geometry.representative_point()
est = gpd.read_file(C.ESTRATOS)[["ESTRATO", "geometry"]].to_crs(d.crs)
cruce = gpd.sjoin(gpd.GeoDataFrame(d[["MANCODIGO"]], geometry=punto, crs=d.crs), est,
                  how="left", predicate="within").drop_duplicates("MANCODIGO")
d = d.merge(cruce[["MANCODIGO", "ESTRATO"]].rename(columns={"ESTRATO": "estrato"}),
            on="MANCODIGO", how="left")
d.loc[d["estrato"] == 0, "estrato"] = np.nan     # 0 es "sin estratificar", no un nivel

# --- morfologia ------------------------------------------------------------
morf = pd.read_csv(C.MORFOLOGIA, dtype={"MANCODIGO": str})
d = d.merge(morf, on="MANCODIGO", how="left")

m = d.to_crs(3116)                               # MAGNA-SIRGAS Bogota, en metros
d["area_manzana_m2"] = m.area.round(1)
d["compacidad"] = (4 * np.pi * m.area / m.length ** 2).round(4)    # 1 = circulo

d["indice_construccion"] = d["area_construida_m2"] / d["area_manzana_m2"]
d["indice_construccion"] = d["indice_construccion"].clip(upper=d["indice_construccion"].quantile(.995))
d["indice_ocupacion"] = (d["area_huella_m2"] / d["area_manzana_m2"]).clip(upper=1)
d["densidad_lotes_ha"] = d["n_lotes"] / (d["area_manzana_m2"] / 1e4)

# IVS: el indice de intensidad edificatoria del proyecto anterior. Primera(s)
# componente(s) de cinco rasgos, solo donde hay al menos 5 construcciones.
cinco = pd.DataFrame({"log_ic": np.log1p(d["indice_construccion"]),
                      "pisos": d["pisos_prom_pond"],
                      "ge3": d["frac_pisos_ge3"],
                      "sub": d["frac_subterraneo"],
                      "log_huella": np.log1p(d["huella_media_m2"])})
ok = (d["n_construcciones"] >= 5) & cinco.notna().all(axis=1)
pca = PCA(random_state=C.SEMILLA).fit(StandardScaler().fit_transform(cinco[ok]))
z = pca.transform(StandardScaler().fit_transform(cinco[ok]))
retenidas = max(int((pca.explained_variance_ > 1).sum()), 1)            # criterio de Kaiser
for j in range(retenidas):                                               # signo: que crezca con la huella
    if np.corrcoef(z[:, j], cinco.loc[ok, "log_huella"])[0, 1] < 0:
        z[:, j] *= -1
pesos = pca.explained_variance_ratio_[:retenidas] / pca.explained_variance_ratio_[:retenidas].sum()
d.loc[ok, "ivs"] = pd.Series(z[:, :retenidas] @ pesos, index=d.index[ok]).rank(pct=True) * 100
print("IVS: %d componentes retenidas, %d manzanas" % (retenidas, ok.sum()))

# --- ubicacion ---------------------------------------------------------------
d["lon"], d["lat"] = punto.x.values, punto.y.values
xy = km(d["lon"], d["lat"])

for nombre, (lo, la) in C.CENTROS.items():
    d["dist_%s_km" % nombre] = np.hypot(*(xy - km(lo, la)[0]).T).round(3)
dist_centros = d[["dist_%s_km" % n for n in C.CENTROS]]
d["dist_centro_cercano_km"] = dist_centros.min(axis=1)
d["centro_cercano"] = dist_centros.idxmin(axis=1).str[5:-3]

# los cerros: el borde oriental de la ciudad, banda por banda de latitud
banda = (d["lat"] / .01).round()
borde = d.groupby(banda)["lon"].quantile(.99).rolling(5, center=True, min_periods=1).median()
d["dist_cerros_km"] = ((banda.map(borde) - d["lon"]).clip(lower=0) * KM_LON).round(3)

lo0, la0 = C.CENTROS["centro_historico"]
rumbo = np.arctan2((d["lon"] - lo0) * KM_LON, (d["lat"] - la0) * KM_LAT)   # 0 = norte
d["azimut_sin"], d["azimut_cos"] = np.sin(rumbo).round(4), np.cos(rumbo).round(4)

arbol = cKDTree(xy)
d["vecinos_500m"] = [len(v) - 1 for v in arbol.query_ball_point(xy, .5)]
d["vecinos_1km"] = [len(v) - 1 for v in arbol.query_ball_point(xy, 1.0)]
d["dist_vecino_8_km"] = arbol.query(xy, k=9)[0][:, 8].round(4)

# --- revision de las centralidades ---------------------------------------------
print("\ncentralidad            manzana mas cercana   mediana COP/m2 a 1 km")
for nombre, (lo, la) in C.CENTROS.items():
    dist, _ = arbol.query(km(lo, la)[0])
    cerca = d["dist_%s_km" % nombre] <= 1
    print("  %-20s %8.0f m           %12s" % (nombre, 1000 * dist,
                                              format(d.loc[cerca, "cop_m2"].median(), ",.0f")))

C.PROC.mkdir(parents=True, exist_ok=True)
d.to_file(C.TABLA)
print("\nescrito %s: %d manzanas x %d columnas" % (C.TABLA.name, len(d), d.shape[1]))
print("con morfologia: %d | con estrato: %d | con uso: %d"
      % (d["n_construcciones"].notna().sum(), d["estrato"].notna().sum(), d["uso"].notna().sum()))
