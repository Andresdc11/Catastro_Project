# Valor del suelo en Bogotá

Consolidado de lo que funcionó en Catastro_ML, rehecho desde los datos. Una tabla
por manzana que junta cuatro fuentes —precio de referencia de Catastro,
morfología de lo construido, estrato y uso— y tres notebooks sobre ella.

## Cómo correrlo

Con el kernel `geoenv`:

```bash
python src/morfologia.py
```

```bash
python src/tabla.py
```

```bash
python src/zonas.py
```

El primero recorre `Construcciones.geojson` (1,8 GB) donde está, en
`../Catastro_ML/`, sin copiarlo: unos 20 s. El segundo arma
`data/processed/manzanas.gpkg`: 41 570 manzanas urbanas × 39 columnas. El
tercero baja de Catastro los nombres de los sectores catastrales y las
localidades, que el 03 usa para ubicar las zonas atípicas.

Después, los notebooks en orden. El 03 necesita lo que deja el 02.

| Notebook | Qué responde |
|---|---|
| `01_valor_suelo` | cuánto vale el suelo, dónde se valoriza, dónde están las empresas y **qué explica el precio** |
| `02_pronostico` | cuánto va a valer hacia 2030 y qué manzanas le ganarían a la ciudad |
| `03_clusters` | cuántos comportamientos de mercado hay y qué zonas destacan |

## Las fuentes

| Archivo | De dónde | Cruce |
|---|---|---|
| `valor_referencia_2026.gpkg` | Catastro, precio y geometría de la manzana | — |
| `valor_referencia_serie.csv.gz` | Catastro, 2017-2026 | código de manzana |
| `uso_predominante_2026.gpkg` | Catastro | código de manzana |
| `estratos_manzana.gpkg` | Catastro | **espacial**: su código no es el mismo |
| `suelo_pot.gpkg` | POT, para quedarse con suelo urbano y de expansión | espacial |
| `Construcciones.geojson` | 2,4 millones de construcciones | primeros 9 dígitos del código del lote |
| `sectores_catastrales.csv` | Catastro, nombre de cada sector (casi siempre el barrio); lo baja `zonas.py` | código de sector |
| `localidades.gpkg` | Catastro, las 20 localidades; lo baja `zonas.py` | espacial |

Las capas de Catastro se copiaron de `Avaluo_bog/Data`. Para bajarlas de nuevo
está `Avaluo_bog/argis1.py`.

Los datos no están en el repositorio (`data/` y `potencial_manzanas/outputs/`
están en `.gitignore`, pesan unos 260 MB). Hay que poner las capas en
`data/raw/` y regenerar `data/processed/` con los scripts y los notebooks.

Las ocho centralidades están en `src/config.py` con coordenadas aproximadas;
`tabla.py` imprime a qué distancia queda la manzana más cercana de cada una.

## Qué cambió frente a Catastro_ML

- **La morfología entra desglosada**, diez variables en vez del IVS, y los índices
  de construcción y ocupación se calculan sobre el área real de la manzana, no
  sobre su caja envolvente.
- **Ocho centralidades** en vez de cuatro.
- **Modelo de nivel de precio** nuevo, validado por sector catastral.
- **Pronóstico**: la elección del método de deriva se revisó con backtest desde
  tres orígenes. El ganador anterior lo era por la ventana; el escenario central
  pasa a ser la mediana de los trienios observados.
- **Clusters**: sale la aceleración, que era la resta de dos variables que ya
  estaban; quedan K-Means, mezcla gaussiana y DBSCAN; la pureza espacial se
  compara contra la referencia correcta. Cada variable lleva su fórmula, y la
  tasa de crecimiento se llama TADC (tasa anual de crecimiento) en todo el
  proyecto. Las atípicas se agrupan en zonas con barrio y localidad:
  `atipicas_zonas.csv`, `atipicas_manzanas.csv` y el mapa `atipicas_mapa.html`.
- La ingesta lee solo las propiedades del GeoJSON: 19 s en vez de 66.

## Lo que sale

- **El precio lo ordenan las centralidades del norte**, no el centro histórico:
  la distancia a la Plaza de Bolívar no se correlaciona con el precio (ρ = −0,05).
- **La morfología suma 0,08 de R² sobre la ubicación sola.** Con las cuatro
  fuentes, el precio de 2026 se estima con R² 0,79 y un error típico del 10 % en
  sectores que el modelo no vio.
- **La valorización es predecible para la ciudad, no para la manzana.** Ninguno de
  diez modelos le gana a "todas crecen igual" con 95 % de confianza; lo único que
  asoma es la reversión a la media. Hacia 2030 la mediana iría de 2,8 M a 3,8 M,
  entre 3,3 M y 4,8 M según el escenario.
- **Los comportamientos de mercado son un continuo.** Cinco grupos útiles que se
  separan por ubicación y estrato, casi nada por morfología.
- **Las atípicas vienen en zonas.** 34 sectores reúnen el 55 % de las 494, y en
  casi todos cambiaron todas el mismo año. El foco mayor es el borde norte de
  Usaquén, con un 2023 hundido que infla su crecimiento reciente.

## Requisitos

geopandas 1.1, pandas 3.0, scikit-learn 1.9, lightgbm 4.7, statsmodels 0.15,
scipy 1.17, matplotlib 3.11.

## Módulo complementario: potencial por manzana

La carpeta `potencial_manzanas/` añade un ranking experimental para 2026–2029.
Compara modelos supervisados con validación temporal y publica por separado un
indicador contextual de valor e intensidad edificatoria. La etiqueta de
oportunidad y sus límites están documentados en
[`potencial_manzanas/README.md`](potencial_manzanas/README.md). Este objetivo
clasifica el grupo superior de crecimiento ajustado por precio; es distinto al
pronóstico continuo del notebook 02.
