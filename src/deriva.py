# -*- coding: utf-8 -*-
"""Medidas de deriva de datos: cuanto cambia una distribucion entre dos momentos.

No confundir con la "deriva de la ciudad" del notebook 02, que es el crecimiento
de la mediana. Formulas, umbrales y lectura en CONFIABILIDAD.md.
"""
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance

PSI_MODERADA = .10
PSI_FUERTE = .25
EPS = 1e-4          # evita log(0) en los tramos vacios


def psi(base, actual, tramos=10):
    """Indice de estabilidad poblacional: sum (a_i - b_i) ln(a_i / b_i).

    Los tramos son los cuantiles de `base`; los empates se funden (una variable
    con 80 % de ceros queda con menos de diez tramos).
    """
    base = pd.Series(base).dropna().to_numpy(dtype=float)
    actual = pd.Series(actual).dropna().to_numpy(dtype=float)
    if len(base) == 0 or len(actual) == 0:
        return np.nan
    cortes = np.unique(np.quantile(base, np.linspace(0, 1, tramos + 1)))
    if len(cortes) < 2:                     # variable constante en la base
        return psi_categorias(base, actual)
    cortes = np.r_[-np.inf, cortes[1:-1], np.inf]
    b = np.maximum(np.histogram(base, cortes)[0] / len(base), EPS)
    a = np.maximum(np.histogram(actual, cortes)[0] / len(actual), EPS)
    return float(np.sum((a - b) * np.log(a / b)))


def psi_categorias(base, actual):
    """PSI para etiquetas (por ejemplo, el peso de cada grupo)."""
    b = pd.Series(base).value_counts(normalize=True)
    a = pd.Series(actual).value_counts(normalize=True)
    cat = b.index.union(a.index)
    b, a = (s.reindex(cat, fill_value=0).clip(lower=EPS) for s in (b, a))
    return float(((a - b) * np.log(a / b)).sum())


def nivel(valor):
    """Semaforo convencional del PSI."""
    if pd.isna(valor):
        return "sin dato"
    return "fuerte" if valor >= PSI_FUERTE else "moderada" if valor >= PSI_MODERADA else "estable"


def tabla_deriva(base, actual, columnas=None):
    """PSI, KS y distancia de Wasserstein por variable, de mayor a menor PSI.

    El KS se da como distancia D, sin valor p: con 40 mil filas cualquier
    diferencia minima sale significativa. Wasserstein va dividida por la
    desviacion tipica de la base, para comparar variables entre si.
    """
    filas = []
    for col in (columnas if columnas is not None else base.columns):
        b, a = base[col].dropna().astype(float), actual[col].dropna().astype(float)
        sd = b.std()
        filas.append({"variable": col, "psi": psi(b, a), "ks_d": ks_2samp(b, a).statistic,
                      "wasserstein_sd": wasserstein_distance(b, a) / sd if sd > 0 else np.nan,
                      "mediana_base": b.median(), "mediana_actual": a.median()})
    t = pd.DataFrame(filas).set_index("variable").sort_values("psi", ascending=False)
    t.insert(1, "nivel", t["psi"].map(nivel))
    return t
