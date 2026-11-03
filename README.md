# Valor del suelo en Bogotá

Analiza el valor de referencia del m² de terreno que publica Catastro, manzana por
manzana, de 2017 a 2026. Responde cuánto vale el suelo, qué variables se asocian con
ese valor, cuánto podría valer hacia 2030 y qué comportamientos de mercado hay.

> **Antes de usar los resultados:** el valor de referencia es un valor administrativo,
> no un precio de transacción, y las cifras son nominales. Ningún resultado se valida
> contra precios reales de mercado. [`CONFIABILIDAD.md`](CONFIABILIDAD.md) dice cuánto
> creerle a cada uno.

## Cómo ejecutarlo

**Necesitas:** Python 3.11, conexión a internet y unos 1,5 GB libres (datos, resultados
y entorno). La primera ejecución tarda unos 15 minutos.

**1. Baja el proyecto y entra a su carpeta:**

```bash
git clone https://github.com/Andresdc11/Catastro_Project.git
cd Catastro_Project
```

**2. Crea el entorno e instala las dependencias.**

En Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En Linux o macOS:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**3. Ejecuta todo:**

```bash
python ejecutar_todo.py
```

Eso es todo: el comando baja los datos, arma la tabla, ejecuta los notebooks con sus
salidas actualizadas y genera el ranking. Si un paso falla, se detiene y dice cuál. Para
retomar desde ahí, usa `python ejecutar_todo.py --desde <paso>`.

El flujo completo se probó en Windows, con Python 3.11, en un entorno nuevo. No se ha
probado en Linux ni en macOS, ni con otra versión de Python. Para usar las construcciones
actuales de Catastro en lugar de las publicadas, lee [Qué resultados esperar](#qué-resultados-esperar).

## Qué hace cada paso

Cada paso usa lo que deja el anterior. Los tiempos son los de la prueba.

| Paso | Archivo | Qué hace | Tiempo |
|---|---|---|---|
| `ingesta` | `src/ingesta.py` | baja las capas de Catastro a `data/raw/` | 8 min |
| `morfologia` | `src/morfologia.py` | deja lista la morfología de cada manzana | 1 s |
| `tabla` | `src/tabla.py` | arma `data/processed/manzanas.gpkg`: 41 570 manzanas × 39 columnas | 15 s |
| `01` | `notebooks/01_valor_suelo.ipynb` | cuánto vale el suelo, dónde se valoriza y qué variables se asocian con el precio | 2 min |
| `02` | `notebooks/02_pronostico.ipynb` | cuánto valdría hacia 2030 y qué manzanas le ganarían a la ciudad | 2 min |
| `03` | `notebooks/03_clusters.ipynb` | qué comportamientos de mercado hay y qué zonas destacan; necesita el 02 | 2 min |
| `potencial` | `potencial_manzanas/run.py` | ranking experimental 2026-2029 | 1 min |
| `informe` | `potencial_manzanas/informe_potencial.ipynb` | informe de ese ranking | 15 s |

Los resultados quedan en `data/processed/` y `potencial_manzanas/outputs/`. Cada notebook
cierra con una sección de confiabilidad y un análisis de resultados.

## Qué resultados esperar

**Por defecto, el flujo reproduce los resultados publicados, mientras Catastro no cambie
sus capas.** Las tablas salieron iguales o con diferencias de redondeo en un entorno
nuevo. Las mayores fueron de 0,002 en el lift del backtest con la regla anterior, de 0,1
en una tabla de ARIMA y de una posición en 4 de las 41 823 manzanas del ranking.

**Por qué puede dejar de coincidir.** El servicio de Catastro entrega el dato vigente, no
una versión fija. El 2026-11-03, las capas que se bajan por defecto coincidían con las de
los resultados publicados, salvo el orden de las filas de `sectores`. Pueden cambiar en
cualquier momento.

**Las construcciones ya cambiaron, y por eso no se bajan por defecto.** Los resultados
publicados usan una copia anterior, de 2 401 061 registros. Su resumen por manzana está
guardado en [`data/referencia/`](data/referencia/README.md). Para usar la versión actual,
que tenía 2 422 631 registros el 2026-11-03, ejecuta:

```bash
python ejecutar_todo.py --vigente
```

Esa opción tarda unos 35 minutos más y cambia estas cifras:

| Resultado | Publicado | Con las construcciones vigentes |
|---|---:|---:|
| R² del precio en sectores no vistos | 0,787 | 0,804 |
| R² dejando fuera localidades completas | 0,42 | 0,38 |
| Modelos que mejoran la línea base con 95 % de confianza | 0 de 10 | 0 de 10 |
| Spearman de la reversión a la media | 0,318 | 0,318 |
| Lift del ranking de potencial | 1,23× | 1,23× |
| Encogimiento del pronóstico | 0,19 | 0,23 |
| Grupos elegidos en el notebook 03 | 5 | **8** |
| Manzanas atípicas | 494 | 513 |

Las conclusiones sobre el crecimiento se mantienen. El número de grupos sí cambia, lo que
confirma que los grupos son una segmentación elegida y no tipos fijos.

**El texto de los notebooks no se actualiza solo.** Ejecutarlos renueva tablas y gráficos,
pero los análisis siguen hablando de los resultados publicados: por ejemplo, de cinco
grupos. Si tus cifras cambian, confía en las salidas y revisa el texto.

Quien tenga el archivo original, `Construcciones.geojson` (1,8 GB), puede ponerlo en una
carpeta `Catastro_ML/` al lado de la del proyecto. Entonces la morfología se recalcula con
él, en unos 20 segundos, en lugar de copiar la guardada.

## Abrir los notebooks

Ya vienen con sus salidas, así que se pueden leer sin ejecutar nada. Para ejecutarlos a
mano, primero corre los pasos `ingesta`, `morfologia` y `tabla`. Desde VS Code o Jupyter,
abre el notebook y elige el kernel de `.venv`. Si pide un kernel llamado `geoenv`, que es
el de la máquina original, cambia a ese mismo.

Jupyter no viene en `requirements.txt`. Si no usas VS Code:
`python -m pip install jupyterlab` y luego `jupyter lab`.

## Las fuentes

| Capa en `ingesta.py` | Archivo en `data/raw/` | Qué trae | Cómo se cruza |
|---|---|---|---|
| `precios` | `valor_referencia_2026.gpkg` | precio y geometría de la manzana | base de la tabla |
| `precios_serie` | `valor_referencia_serie.csv.gz` | precio de 2017 a 2026 | código de manzana |
| `usos` | `uso_predominante_2026.gpkg` | uso económico predominante | código de manzana |
| `estratos` | `estratos_manzana.gpkg` | estrato socioeconómico | **espacial**: su código no es el mismo |
| `suelo` | `suelo_pot.gpkg` | clases de suelo del POT, para el perímetro urbano | espacial |
| `construcciones` (opcional) | `construcciones.csv.gz` | 2,4 millones de construcciones, solo con `--vigente` | primeros 9 dígitos del código del lote |
| `sectores` | `sectores_catastrales.csv` | nombre de cada sector, casi siempre el barrio | código de sector |
| `localidades` | `localidades.gpkg` | las 20 localidades | espacial |

Las capas salen del [servicio ArcGIS REST de
Catastro](https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services). En el
repositorio solo está la morfología de referencia; lo demás se descarga. La fórmula de cada variable está al inicio de `src/tabla.py` y
de `src/morfologia.py`, y en [`GUIA_VARIABLES.html`](GUIA_VARIABLES.html).

### Descargar por partes

`src/ingesta.py` pregunta cuántos registros tiene cada capa, los pide de 2 000 en 2 000 y
comprueba que llegaron todos. Solo entonces escribe el archivo, así que un corte no deja
un archivo incompleto.

| Comando | Qué hace |
|---|---|
| `python src/ingesta.py --listar` | muestra el catálogo y lo que ya está en disco |
| `python src/ingesta.py` | baja las capas que falten y no toca las demás |
| `python src/ingesta.py --vigente` | lo mismo, y además las construcciones actuales (unos 35 min más) |
| `python src/ingesta.py suelo precios` | baja solo esas capas |
| `python src/ingesta.py --forzar` | reemplaza todas las capas |
| `python src/ingesta.py --destino CARPETA` | guarda en otra carpeta y no toca `data/raw/` |

Para ver qué cambió en el servicio antes de reemplazar nada, usa `--destino`.
`python src/zonas.py` es un atajo que actualiza solo los sectores y las localidades.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `py` o `python3.11` no se reconoce | instala Python 3.11 desde python.org |
| PowerShell bloquea `Activate.ps1` | ejecuta `Set-ExecutionPolicy -Scope Process RemoteSigned` y vuelve a activar |
| Error de red o `llegaron X de Y registros` | el servicio falla a ratos: vuelve a ejecutar. Las capas ya guardadas se conservan, pero la capa en curso empieza de nuevo |
| Un notebook pide el kernel `geoenv` | elige el kernel de `.venv` |
| Errores de DLL con conda | activa el entorno con `conda activate`, no llames a su `python.exe` directamente |
| `git status` muestra notebooks modificados | es normal, porque `ejecutar_todo.py` guarda las salidas nuevas. `git restore notebooks potencial_manzanas/informe_potencial.ipynb` recupera las publicadas |

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

## Módulo complementario: potencial por manzana

La carpeta `potencial_manzanas/` añade un ranking experimental para 2026–2029.
Compara modelos supervisados con validación temporal y publica por separado un
indicador contextual de valor e intensidad edificatoria. La etiqueta de
oportunidad y sus límites están documentados en
[`potencial_manzanas/README.md`](potencial_manzanas/README.md). Este objetivo
clasifica el grupo superior de crecimiento ajustado por precio; es distinto al
pronóstico continuo del notebook 02.

**Señal modesta:** al corregir su backtest, que se solapaba con el periodo validado, el
lift bajó de 1,74× a 1,23×. El principio del ranking son manzanas que acaban de caer, y
van marcadas (ver [`CONFIABILIDAD.md`](CONFIABILIDAD.md)).

## Qué cambió frente a Catastro_ML

Este proyecto consolida lo que funcionó en un proyecto anterior, rehecho desde los datos.

- **La morfología entra desglosada**, diez variables en vez del IVS, y los índices
  de construcción y ocupación se calculan sobre el área real de la manzana, no
  sobre su caja envolvente.
- **Ocho centralidades** en vez de cuatro. Sus coordenadas son aproximadas y están en
  `src/config.py`; `tabla.py` imprime a qué distancia queda la manzana más cercana de
  cada una.
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
