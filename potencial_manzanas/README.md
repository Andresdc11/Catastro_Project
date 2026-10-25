# Potencial de valorización por manzana

Módulo complementario al proyecto principal. Lee sus capas procesadas y la serie
de avalúos para estimar qué manzanas podrían quedar en el grupo de mayor
valorización relativa durante un horizonte de tres años. No altera los notebooks,
datos ni resultados existentes.

## Qué estima

La etiqueta de entrenamiento es la oportunidad observada en cada ventana histórica
de tres años: crecimiento anual del avalúo menos el crecimiento esperado para una
manzana con un precio inicial parecido. Se marca como oportunidad alta el 20 % con
mayor residuo de cada ventana. Así el objetivo no es simplemente encontrar las
manzanas más baratas ni proyectar la inflación de toda la ciudad.

El modelo ordena manzanas por su semejanza con ese comportamiento histórico. Su
salida es un puntaje relativo; no es un precio futuro, una probabilidad calibrada
de rentabilidad ni una recomendación de inversión. El avalúo de Catastro es un
valor administrativo de referencia, no un precio de transacción.

Este objetivo de clasificación es distinto al pronóstico continuo del notebook
02: allí ningún modelo mejoró de forma concluyente el error del crecimiento de
todas las manzanas. Aquí se evalúa si el modelo concentra más etiquetas del top
20 % ajustado por precio en el top 20 % de su ranking. El lift de clasificación
no significa que se pueda pronosticar con precisión el avalúo o el rendimiento
en pesos.

La validación es temporal y de origen móvil. Para predecir la oportunidad de una
ventana, el modelo solo se ajusta con ventanas anteriores. Las variables del
modelo supervisado son la trayectoria de avalúos conocida al inicio de la ventana
y rasgos espaciales estables. Las especificaciones de edificaciones están
disponibles únicamente como foto actual; por eso se publican en un indicador
contextual separado y no contaminan el backtest temporal.

## Indicador de edificaciones

El indicador contextual combina el percentil del valor de referencia por m² y el
percentil inverso de la intensidad edificatoria actual (índice de construcción,
ocupación y pisos). Resalta manzanas relativamente costosas y con menor intensidad
construida. Sirve para priorizar revisión, no demuestra que un predio pueda
construir más: faltan normas POT de edificabilidad por predio y polígonos
catastrales de lote. El resultado permanece al nivel de manzana, que es el nivel
del avalúo disponible.

## Ejecución

Desde esta carpeta, con el entorno `geoenv` del proyecto:

    conda run -n geoenv python run.py

Opciones:

    python run.py --horizonte 3 --fraccion-alta 0.20

Las fuentes se leen desde `../data/processed` y `../data/raw`; no se copian.
El flujo no necesita el GeoJSON grande de construcciones porque utiliza la
morfología ya agregada en `manzanas.gpkg`.

## Archivos generados

- `informe_potencial.ipynb`: informe EDA ejecutado, métricas del backtest, ranking y análisis de límites.
- `outputs/potencial_2026_2029.csv.gz`: ranking supervisado por manzana.
- `outputs/contexto_edificaciones_2026.csv.gz`: valor e intensidad edificatoria
  contextual, con bandera de alto valor y baja intensidad.
- `outputs/backtest_metricas.csv`: resultados por origen y modelo, comparados
  con la línea base sin señal.
- `outputs/backtest_resumen.csv`: promedio de las validaciones temporales y
  referencia de desempeño.
- `outputs/backtest_predicciones.csv.gz`: predicciones fuera de tiempo usadas
  para calcular las métricas.
- `outputs/entrenamiento_historico.csv.gz`: ventanas y etiquetas que alimentan
  el modelo.
- `outputs/importancia_variables.csv`: importancia por permutación del mejor
  modelo en el último origen de validación.
- `outputs/modelo_final.joblib`: modelo ajustado para generar el ranking actual.
- `outputs/informe_ejecucion.json`: fechas, umbrales, variables y advertencias.

Una mejora real sobre la línea base debe repetirse en varios orígenes. Si los
modelos no muestran lift estable, el ranking se debe tratar solo como exploratorio.
El horizonte final (2026–2029) todavía no tiene avalúos observados, así que su
desempeño futuro no puede validarse con los datos actuales.
