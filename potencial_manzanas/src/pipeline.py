"""Preparación, validación temporal y ranking de oportunidad por manzana."""
from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANZANAS_PATH = PROJECT_ROOT / "data" / "processed" / "manzanas.gpkg"
SERIE_PATH = PROJECT_ROOT / "data" / "raw" / "valor_referencia_serie.csv.gz"
CLUSTERS_PATH = PROJECT_ROOT / "data" / "processed" / "clusters_manzanas.csv.gz"
OUTPUT_DIR = PACKAGE_DIR / "outputs"
SEED = 42

HISTORY_FEATURES = [
    "log_precio_inicio",
    "precio_relativo_ciudad",
    "crecimiento_1a_previo",
    "crecimiento_3a_previo",
    "volatilidad_3a_previa",
    "fraccion_sin_cambio_3a",
    "salto_maximo_3a",
]
SPATIAL_FEATURES = [
    "lon", "lat", "area_manzana_m2", "compacidad",
    "dist_centro_historico_km", "dist_centro_internacional_km",
    "dist_zona_t_km", "dist_calle_100_km", "dist_usaquen_km",
    "dist_salitre_km", "dist_aeropuerto_km", "dist_centro_sur_km",
    "dist_centro_cercano_km", "dist_cerros_km", "azimut_sin",
    "azimut_cos", "vecinos_500m", "vecinos_1km", "dist_vecino_8_km",
]
MORPHOLOGY_FEATURES = [
    "indice_construccion", "indice_ocupacion", "pisos_prom_pond",
    "pisos_max", "frac_pisos_ge3", "frac_subterraneo", "huella_media_m2",
    "densidad_lotes_ha", "n_construcciones", "n_lotes",
]


def cargar_datos():
    """Lee las fuentes existentes, conservando códigos como texto."""
    for path in (MANZANAS_PATH, SERIE_PATH):
        if not path.exists():
            raise FileNotFoundError("No se encuentra la fuente requerida: %s" % path)

    manzanas = gpd.read_file(MANZANAS_PATH)
    manzanas["MANCODIGO"] = manzanas["MANCODIGO"].astype(str).str.zfill(9)
    manzanas["sector"] = manzanas["MANCODIGO"].str[:6]
    serie = pd.read_csv(SERIE_PATH, dtype={"MANCODIGO": str})
    serie["MANCODIGO"] = serie["MANCODIGO"].astype(str).str.zfill(9)
    serie["ANO"] = pd.to_numeric(serie["ANO"], errors="coerce")
    serie["V_REF"] = pd.to_numeric(serie["V_REF"], errors="coerce")
    serie = serie.dropna(subset=["MANCODIGO", "ANO", "V_REF"])
    serie = serie[serie["V_REF"] > 0]
    panel = serie.pivot_table(index="MANCODIGO", columns="ANO", values="V_REF",
                              aggfunc="median").sort_index(axis=1)
    panel.columns = panel.columns.astype(int)
    panel = panel.astype(float)

    numeric_static = [c for c in SPATIAL_FEATURES if c in manzanas.columns]
    static_cols = ["MANCODIGO", "sector"] + numeric_static
    static = (manzanas[static_cols].drop_duplicates("MANCODIGO")
              .set_index("MANCODIGO"))
    static["sector"] = static["sector"].astype(str)
    return manzanas, panel, static


def construir_features(panel, static, origen):
    """Crea rasgos conocidos al inicio del periodo, sin mirar el futuro."""
    log_panel = np.log(panel.where(panel > 0))
    if origen not in log_panel.columns:
        raise ValueError("No hay valor para el año de origen %s" % origen)

    precio = panel[origen]
    log_precio = log_panel[origen]
    validos = precio.notna() & log_precio.notna()
    filas = pd.DataFrame(index=panel.index[validos])
    filas["log_precio_inicio"] = log_precio.loc[validos]
    mediana_ciudad = log_precio.loc[validos].median()
    filas["precio_relativo_ciudad"] = filas["log_precio_inicio"] - mediana_ciudad

    if origen - 1 in log_panel.columns:
        filas["crecimiento_1a_previo"] = (
            log_panel[origen] - log_panel[origen - 1]).reindex(filas.index)
    else:
        filas["crecimiento_1a_previo"] = np.nan

    if origen - 3 in log_panel.columns:
        filas["crecimiento_3a_previo"] = (
            (log_panel[origen] - log_panel[origen - 3]) / 3).reindex(filas.index)
    else:
        filas["crecimiento_3a_previo"] = np.nan

    cambios = []
    congelados = []
    for year in range(origen - 2, origen + 1):
        if year - 1 not in panel.columns or year not in panel.columns:
            continue
        previo = panel[year - 1]
        actual = panel[year]
        cambio = (log_panel[year] - log_panel[year - 1]).reindex(filas.index)
        cambios.append(cambio.rename(str(year)))
        igual = (previo.notna() & actual.notna()
                 & np.isclose(previo, actual, rtol=0, atol=1e-12))
        congelados.append(igual.reindex(filas.index).astype(float).rename(str(year)))

    if cambios:
        cambios_df = pd.concat(cambios, axis=1)
        filas["volatilidad_3a_previa"] = cambios_df.std(axis=1, skipna=True)
        filas["salto_maximo_3a"] = cambios_df.abs().max(axis=1, skipna=True)
    else:
        filas["volatilidad_3a_previa"] = np.nan
        filas["salto_maximo_3a"] = np.nan
    if congelados:
        filas["fraccion_sin_cambio_3a"] = pd.concat(congelados, axis=1).mean(axis=1)
    else:
        filas["fraccion_sin_cambio_3a"] = np.nan

    filas = filas.join(static, how="left")
    filas["MANCODIGO"] = filas.index
    filas["origen"] = int(origen)
    filas["precio_inicio"] = precio.reindex(filas.index)
    return filas.reset_index(drop=True)


def construir_panel_entrenamiento(panel, static, horizonte, fraccion_alta):
    """Construye ejemplos retrospectivos y una etiqueta ajustada por precio."""
    years = [int(y) for y in panel.columns]
    rows = []
    ventanas_descartadas = []
    for origen in years:
        fin = origen + horizonte
        if fin not in years:
            continue
        start_price = panel[origen]
        end_price = panel[fin]
        valid = start_price.gt(0) & end_price.gt(0)
        if not valid.any():
            continue

        if fin > min(years):
            previo_fin = panel[fin - 1]
            observables = end_price.notna() & previo_fin.notna() & valid
            if observables.any():
                congeladas = np.isclose(end_price[observables], previo_fin[observables],
                                        rtol=0, atol=1e-12).mean()
                if congeladas >= 0.80:
                    ventanas_descartadas.append({"origen": origen, "fin": fin,
                                                 "motivo": "mas_del_80_pct_sin_cambio"})
                    continue

        ids = panel.index[valid]
        growth = (np.log(end_price.loc[ids]) - np.log(start_price.loc[ids])) / horizonte
        log_start = np.log(start_price.loc[ids])
        iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
        expected = iso.fit_transform(log_start.to_numpy(), growth.to_numpy())
        opportunity = pd.Series(growth.to_numpy() - expected, index=ids)
        top_n = max(1, int(math.ceil(fraccion_alta * len(opportunity))))
        top = opportunity.rank(method="first", ascending=False).le(top_n)

        features = construir_features(panel, static, origen).set_index("MANCODIGO", drop=False)
        labels = pd.DataFrame({
            "crecimiento_log_anual": growth,
            "crecimiento_esperado_por_precio": pd.Series(expected, index=ids),
            "oportunidad_residual": opportunity,
            "alto_potencial_historico": top.astype(int),
            "fin": fin,
        })
        joined = features.join(labels, how="inner")
        joined["sector"] = joined["sector"].astype(str)
        rows.append(joined.reset_index(drop=True))

    if not rows:
        raise ValueError("No hay ventanas válidas para el horizonte indicado")
    result = pd.concat(rows, ignore_index=True)
    result["alto_potencial_historico"] = result["alto_potencial_historico"].astype(int)
    return result, ventanas_descartadas


def crear_modelo(nombre):
    if nombre.startswith("logit"):
        return make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            StandardScaler(),
            LogisticRegression(C=0.5, max_iter=1200, random_state=SEED),
        )
    if nombre == "hist_gradient":
        return make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=15,
                                           l2_regularization=1.0,
                                           early_stopping=False, random_state=SEED),
        )
    raise ValueError("Modelo desconocido: %s" % nombre)


def precision_en_top(y, score, fraccion_alta):
    """Precisión esperada al top-k, repartiendo empates al azar en el corte."""
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    n_top = max(1, int(math.ceil(fraccion_alta * len(y))))
    cutoff = np.partition(score, len(score) - n_top)[len(score) - n_top]
    arriba = score > cutoff
    empatados = score == cutoff
    cupos_empate = n_top - int(arriba.sum())
    positivas = y[arriba].sum() + cupos_empate * y[empatados].mean()
    return float(positivas / n_top)


def metricas(y, score, fraccion_alta):
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    prevalence = float(y.mean())
    precision_top = precision_en_top(y, score, fraccion_alta)
    return {
        "promedio_precision": float(average_precision_score(y, score)),
        "auc_roc": float(roc_auc_score(y, score)) if np.unique(y).size > 1 else np.nan,
        "precision_top_fraccion": precision_top,
        "prevalencia": prevalence,
        "lift_top_fraccion": precision_top / prevalence if prevalence else np.nan,
        "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
        "n": int(len(y)),
    }


def validar_temporalmente(training, fraccion_alta):
    """Predice cada origen usando solo ventanas anteriores."""
    history_cols = [c for c in HISTORY_FEATURES if c in training.columns]
    spatial_cols = [c for c in SPATIAL_FEATURES if c in training.columns]
    specs = {
        "logit_historia": history_cols,
        "logit_historia_espacio": history_cols + spatial_cols,
        "hist_gradient": history_cols + spatial_cols,
    }
    origins = sorted(training["origen"].unique())
    detail, prediction_frames = [], []
    for valid_origin in origins:
        train = training[training["origen"] < valid_origin]
        valid = training[training["origen"] == valid_origin]
        if train["origen"].nunique() < 2 or valid.empty:
            continue
        y_train = train["alto_potencial_historico"].to_numpy()
        y_valid = valid["alto_potencial_historico"].to_numpy()
        baseline = np.full(len(valid), y_train.mean(), dtype=float)
        m = metricas(y_valid, baseline, fraccion_alta)
        detail.append({"modelo": "linea_base_sin_senal", "origen_validacion": int(valid_origin), **m})
        prediction_frames.append(pd.DataFrame({
            "MANCODIGO": valid["MANCODIGO"].to_numpy(),
            "sector": valid["sector"].astype(str).to_numpy(),
            "origen": int(valid_origin),
            "modelo": "linea_base_sin_senal",
            "real_alto_potencial": y_valid,
            "score": baseline,
        }))

        for name, cols in specs.items():
            cols = [c for c in cols if c in train.columns and c in valid.columns]
            model = crear_modelo(name)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(train[cols], y_train)
            score = model.predict_proba(valid[cols])[:, 1]
            m = metricas(y_valid, score, fraccion_alta)
            detail.append({"modelo": name, "origen_validacion": int(valid_origin), **m})
            prediction_frames.append(pd.DataFrame({
                "MANCODIGO": valid["MANCODIGO"].to_numpy(),
                "sector": valid["sector"].astype(str).to_numpy(),
                "origen": int(valid_origin),
                "modelo": name,
                "real_alto_potencial": y_valid,
                "score": score,
            }))

    metrics_df = pd.DataFrame(detail)
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    if metrics_df.empty:
        raise ValueError("Faltan orígenes previos para realizar el backtest temporal")
    return metrics_df, predictions, specs


def bootstrap_lift_por_sector(predicciones, fraccion_alta, n_boot=300):
    """Intervalo de incertidumbre del lift remuestreando sectores completos."""
    if predicciones.empty or predicciones["sector"].nunique() < 2:
        return {"lift_media": np.nan, "lift_ic95_inferior": np.nan,
                "lift_ic95_superior": np.nan, "sectores_bootstrap": 0}
    y = predicciones["real_alto_potencial"].to_numpy(dtype=int)
    s = predicciones["score"].to_numpy(dtype=float)
    sectors = np.asarray(predicciones["sector"], dtype=str)
    groups = {sector: np.flatnonzero(sectors == sector) for sector in np.unique(sectors)}
    keys = np.array(list(groups), dtype=object)
    rng = np.random.default_rng(SEED)
    lifts = []
    for _ in range(n_boot):
        chosen = rng.choice(keys, size=len(keys), replace=True)
        idx = np.concatenate([groups[key] for key in chosen])
        if len(idx) < 2:
            continue
        prevalence = y[idx].mean()
        if prevalence > 0:
            precision = precision_en_top(y[idx], s[idx], fraccion_alta)
            lifts.append(float(precision / prevalence))
    observed = metricas(y, s, fraccion_alta)["lift_top_fraccion"]
    if not lifts:
        return {"lift_media": observed, "lift_ic95_inferior": np.nan,
                "lift_ic95_superior": np.nan, "sectores_bootstrap": int(len(keys))}
    low, high = np.percentile(lifts, [2.5, 97.5])
    return {"lift_media": float(observed), "lift_ic95_inferior": float(low),
            "lift_ic95_superior": float(high), "sectores_bootstrap": int(len(keys))}


def crear_contexto_morfologico(manzanas):
    """Calcula un ranking exploratorio de valor alto e intensidad baja."""
    available = [c for c in MORPHOLOGY_FEATURES if c in manzanas.columns]
    cols = ["MANCODIGO", "sector", "cop_m2"] + available
    context = manzanas[cols].copy().drop_duplicates("MANCODIGO")
    context["MANCODIGO"] = context["MANCODIGO"].astype(str).str.zfill(9)
    context["sector"] = context["MANCODIGO"].str[:6]
    context = context.rename(columns={"cop_m2": "cop_m2_2026"})
    intensity_parts = []
    for col in ["indice_construccion", "indice_ocupacion", "pisos_prom_pond"]:
        if col in context.columns:
            value = pd.to_numeric(context[col], errors="coerce")
            pct = value.rank(pct=True, method="average")
            context[col + "_percentil"] = pct
            intensity_parts.append(pct.rename(col))
    price_pct = pd.to_numeric(context["cop_m2_2026"], errors="coerce").rank(
        pct=True, method="average")
    context["valor_m2_percentil"] = price_pct
    intensity_pct = pd.concat(intensity_parts, axis=1).mean(axis=1) if intensity_parts else np.nan
    context["intensidad_edificatoria_percentil"] = intensity_pct
    context["baja_intensidad_percentil"] = 1 - intensity_pct
    context["score_contextual_0_100"] = 100 * (
        context["valor_m2_percentil"] + context["baja_intensidad_percentil"]
    ) / 2
    context["valor_alto_baja_intensidad"] = (
        (context["valor_m2_percentil"] >= 0.75)
        & (context["intensidad_edificatoria_percentil"] <= 0.25)
    )
    context["interpretacion"] = (
        "Filtro de revisión: precio relativo alto e intensidad edificatoria baja; "
        "no equivale a capacidad legal de construcción"
    )

    if CLUSTERS_PATH.exists():
        clusters = pd.read_csv(CLUSTERS_PATH, dtype={"MANCODIGO": str})
        keep = [c for c in ["MANCODIGO", "oportunidad_pct", "n_detectores", "atipica"]
                if c in clusters.columns]
        clusters = clusters[keep].drop_duplicates("MANCODIGO")
        context = context.merge(clusters, on="MANCODIGO", how="left")
    return context.sort_values("score_contextual_0_100", ascending=False)


def guardar_csv(frame, path):
    frame.to_csv(path, index=False, compression="gzip" if str(path).endswith(".gz") else None)


def ejecutar(horizonte=3, fraccion_alta=0.20):
    if horizonte < 1:
        raise ValueError("El horizonte debe ser al menos un año")
    if not 0 < fraccion_alta < 0.5:
        raise ValueError("La fracción alta debe ser mayor que 0 y menor que 0.5")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Leyendo fuentes del proyecto…")
    manzanas, panel, static = cargar_datos()
    print("  %s manzanas | %s años de avalúos (%s–%s)" % (
        len(manzanas), len(panel.columns), panel.columns.min(), panel.columns.max()))

    print("Construyendo ventanas históricas de %s años…" % horizonte)
    training, discarded = construir_panel_entrenamiento(panel, static, horizonte,
                                                          fraccion_alta)
    print("  %s ejemplos | %s ventanas | %s etiquetas altas" % (
        len(training), training["origen"].nunique(),
        int(training["alto_potencial_historico"].sum())))
    guardar_csv(training, OUTPUT_DIR / "entrenamiento_historico.csv.gz")

    print("Ejecutando validación temporal de origen móvil…")
    metrics_df, predictions, specs = validar_temporalmente(training, fraccion_alta)
    guardar_csv(metrics_df, OUTPUT_DIR / "backtest_metricas.csv")
    guardar_csv(predictions, OUTPUT_DIR / "backtest_predicciones.csv.gz")
    summary = (metrics_df.groupby("modelo", as_index=False)
               .agg(origenes=("origen_validacion", "nunique"),
                    promedio_precision=("promedio_precision", "mean"),
                    auc_roc=("auc_roc", "mean"),
                    precision_top_fraccion=("precision_top_fraccion", "mean"),
                    lift_top_fraccion=("lift_top_fraccion", "mean"),
                    brier=("brier", "mean")))
    summary = summary.sort_values(["promedio_precision", "lift_top_fraccion"],
                                  ascending=False)
    guardar_csv(summary, OUTPUT_DIR / "backtest_resumen.csv")

    candidates = summary[summary["modelo"] != "linea_base_sin_senal"]
    if candidates.empty:
        raise ValueError("No se pudo ajustar un modelo supervisado")
    chosen = str(candidates.iloc[0]["modelo"])
    best_oof = predictions[predictions["modelo"] == chosen].copy()
    ci = bootstrap_lift_por_sector(best_oof, fraccion_alta)
    latest_origin = int(training["origen"].max())
    latest_fold = metrics_df[(metrics_df["origen_validacion"] == latest_origin)
                             & (metrics_df["modelo"] == chosen)]
    latest_lift = float(latest_fold["lift_top_fraccion"].iloc[0]) if not latest_fold.empty else np.nan
    backtest_supported = bool(ci["lift_ic95_inferior"] > 1.0 and latest_lift > 1.0)

    history_cols = [c for c in HISTORY_FEATURES if c in training.columns]
    spatial_cols = [c for c in SPATIAL_FEATURES if c in training.columns]
    model_cols = history_cols if chosen == "logit_historia" else history_cols + spatial_cols
    if chosen == "hist_gradient":
        model_cols = history_cols + spatial_cols
    final_model = crear_modelo(chosen)
    final_model.fit(training[model_cols], training["alto_potencial_historico"].to_numpy())
    final_origin = int(panel.columns.max())
    future_end = final_origin + horizonte
    future_features = construir_features(panel, static, final_origin)
    future_features = future_features.dropna(subset=["precio_inicio"])
    scores = final_model.predict_proba(future_features[model_cols])[:, 1]
    forecast = future_features[["MANCODIGO", "sector", "precio_inicio", "origen"]].copy()
    forecast["MANCODIGO"] = forecast["MANCODIGO"].astype(str).str.zfill(9)
    forecast["sector"] = forecast["MANCODIGO"].str[:6]
    forecast = forecast.rename(columns={"precio_inicio": "cop_m2_inicio",
                                        "origen": "ano_origen"})
    forecast["horizonte_anos"] = horizonte
    forecast["ano_fin_objetivo"] = future_end
    forecast["score_modelo"] = scores
    forecast["puesto_ranking"] = forecast["score_modelo"].rank(
        method="first", ascending=False).astype(int)
    forecast["ranking_percentil"] = (
        len(forecast) - forecast["puesto_ranking"] + 1) / len(forecast)
    forecast["score_potencial_0_100"] = 100 * forecast["ranking_percentil"]
    forecast["candidato_top_fraccion"] = (
        forecast["puesto_ranking"] <= int(math.ceil(fraccion_alta * len(forecast))))
    forecast["modelo"] = chosen
    forecast["lift_ic95_inferior_backtest"] = ci["lift_ic95_inferior"]
    forecast["lift_ic95_superior_backtest"] = ci["lift_ic95_superior"]
    forecast["respaldo_temporal"] = "si" if backtest_supported else "debil_o_no_concluyente"
    forecast = forecast.sort_values("score_potencial_0_100", ascending=False)
    guardar_csv(forecast, OUTPUT_DIR / "potencial_2026_2029.csv.gz")
    joblib.dump({"modelo": final_model, "variables": model_cols,
                 "modelo_nombre": chosen, "horizonte": horizonte,
                 "fraccion_alta": fraccion_alta}, OUTPUT_DIR / "modelo_final.joblib")

    latest_valid = training[training["origen"] == latest_origin]
    latest_cols = [c for c in model_cols if c in latest_valid.columns]
    if len(latest_valid) > 0:
        fitted_for_importance = crear_modelo(chosen)
        earlier = training[training["origen"] < latest_origin]
        fitted_for_importance.fit(earlier[latest_cols], earlier["alto_potencial_historico"].to_numpy())
        perm = permutation_importance(
            fitted_for_importance, latest_valid[latest_cols],
            latest_valid["alto_potencial_historico"].to_numpy(),
            scoring="average_precision", n_repeats=3, random_state=SEED, n_jobs=1)
        importance = pd.DataFrame({"variable": latest_cols,
                                   "caida_promedio_precision": perm.importances_mean,
                                   "desvio": perm.importances_std})
        importance = importance.sort_values("caida_promedio_precision", ascending=False)
        guardar_csv(importance, OUTPUT_DIR / "importancia_variables.csv")

    context = crear_contexto_morfologico(manzanas)
    guardar_csv(context, OUTPUT_DIR / "contexto_edificaciones_2026.csv.gz")

    chosen_latest = metrics_df[(metrics_df["modelo"] == chosen)
                               & (metrics_df["origen_validacion"] == latest_origin)]
    baseline_latest = metrics_df[(metrics_df["modelo"] == "linea_base_sin_senal")
                                 & (metrics_df["origen_validacion"] == latest_origin)]
    top = forecast.head(20)[["puesto_ranking", "MANCODIGO", "cop_m2_inicio",
                             "score_potencial_0_100"]]
    if not chosen_latest.empty and not baseline_latest.empty:
        selected_metrics = chosen_latest.iloc[0]
        baseline_metrics = baseline_latest.iloc[0]
        metric_lines = [
            "| Medida | Modelo | Sin señal |",
            "|---|---:|---:|",
            "| Average precision | %.3f | %.3f |" % (
                selected_metrics["promedio_precision"], baseline_metrics["promedio_precision"]),
            "| Precisión dentro del top %.0f%% | %.1f%% | %.1f%% |" % (
                fraccion_alta * 100, 100 * selected_metrics["precision_top_fraccion"],
                100 * baseline_metrics["precision_top_fraccion"]),
            "| Lift del top | %.2f× | %.2f× |" % (
                selected_metrics["lift_top_fraccion"], baseline_metrics["lift_top_fraccion"]),
        ]
    else:
        metric_lines = ["No hay una ventana final suficiente para resumir métricas."]
    top_table = [
        "| Puesto | MANCODIGO | Avalúo inicial COP/m² | Puntaje |",
        "|---:|---|---:|---:|",
    ]
    for row in top.itertuples(index=False, name=None):
        top_table.append("| %d | %s | %.0f | %.3f |" % (row[0], row[1], row[2], row[3]))
    summary_md = [
        "# Ejecución del ranking de potencial",
        "",
        "- Unidad: manzana.",
        "- Corte y horizonte: %s–%s (%s años)." % (final_origin, future_end, horizonte),
        "- Objetivo histórico: grupo superior del %.0f%% en crecimiento anual ajustado por precio inicial." % (
            fraccion_alta * 100),
        "- Mejor modelo por promedio de average precision: `%s`." % chosen,
        "- Lift fuera de tiempo agregado: %.2f× (IC sectorial 95%% %.2f–%.2f)." % (
            ci["lift_media"], ci["lift_ic95_inferior"], ci["lift_ic95_superior"]),
        "- Validación temporal más reciente: origen %s." % latest_origin,
        "",
        "## Última ventana de validación",
        "",
        *metric_lines,
        "",
        "El ranking futuro es exploratorio: el puntaje del clasificador no se calibró como probabilidad de rentabilidad y aún no hay avalúos 2029 para validarlo.",
        "El intervalo remuestrea sectores sobre predicciones fuera de tiempo; resume incertidumbre espacial, no toda la variación entre periodos.",
        "",
        "## Primeras 20 manzanas del ranking",
        "",
        *top_table,
        "",
        "## Lectura del indicador de edificaciones",
        "",
        "Consultar `contexto_edificaciones_2026.csv.gz`. Sus candidatos combinan valor relativo alto e intensidad edificatoria baja; no representan permisos ni edificabilidad reglamentaria.",
    ]
    (OUTPUT_DIR / "resumen_ejecucion.md").write_text("\n".join(summary_md) + "\n",
                                                     encoding="utf-8")

    report = {
        "unidad": "manzana",
        "anio_corte": final_origin,
        "horizonte_anos": horizonte,
        "anio_fin_objetivo": future_end,
        "fraccion_alta_historica": fraccion_alta,
        "criterio_objetivo": "crecimiento anual menos isotónica decreciente de precio inicial; grupo superior",
        "ventanas_entrenamiento": sorted(int(x) for x in training["origen"].unique()),
        "ventanas_descartadas": discarded,
        "origen_validacion_mas_reciente": latest_origin,
        "mejor_modelo_por_promedio_precision": chosen,
        "lift_oof_sector_bootstrap": ci,
        "lift_validacion_mas_reciente": latest_lift,
        "respaldo_temporal": backtest_supported,
        "variables_modelo": model_cols,
        "morfologia_en_modelo_supervisado": False,
        "advertencias": [
            "El objetivo es valorizacion catastral relativa, no precio de transaccion ni rentabilidad.",
            "El puntaje final ordena manzanas; no es una probabilidad calibrada ni un valor futuro en COP.",
            "La morfologia actual se informa aparte por falta de snapshots historicos.",
            "La capacidad de desarrollo legal no se puede determinar sin parametros POT por predio.",
            "El periodo objetivo futuro aun no tiene avalúos observados para validarlo.",
            "El intervalo bootstrap por sector no mide toda la variacion temporal entre ventanas.",
        ],
    }
    with (OUTPUT_DIR / "informe_ejecucion.json").open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, allow_nan=True)

    print("Modelo elegido: %s | lift OOF %.2f (IC95%% %.2f–%.2f)" % (
        chosen, ci["lift_media"], ci["lift_ic95_inferior"], ci["lift_ic95_superior"]))
    print("Respaldo temporal: %s | ranking para %s–%s" % (
        "si" if backtest_supported else "debil/no concluyente", final_origin, future_end))
    print("Resultados escritos en %s" % OUTPUT_DIR)
