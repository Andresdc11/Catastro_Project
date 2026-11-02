# Confiabilidad y deriva

Qué tanto creerle a cada resultado del proyecto, cómo se mide y qué vigilar cuando
salga un dato nuevo. Corte: serie de Catastro 2017-2026. Cada cifra sale de la sección
"Confiabilidad y deriva" del notebook indicado.

> El valor de referencia de Catastro es un **valor administrativo**, no un precio de
> transacción. Todas las medidas de este documento dicen qué tan bien se describe o
> anticipa ese valor; **ninguna valida frente a precios reales de mercado.**

## Resumen

La columna "Confianza" es una valoración de criterio a partir de las métricas, no una
medida calculada.

| Resultado | Confianza | Por qué | Úsalo para | No lo uses para |
|---|---|---|---|---|
| Precio estimado 2026 (`01`) | **Alta** para comparar, **media** para una manzana | R² 0,79 (IC 0,76-0,81) en sectores no vistos; margen del 90 % de −34 % a +52 % | ubicar una manzana frente a la ciudad | tasar un lote |
| Orden por reversión a la media (`02`) | **Media** | Spearman 0,32 (IC 0,26-0,37); señal en las siete ventanas | filtrar candidatas | calcular un retorno |
| Crecimiento relativo por manzana (`02`) | **Baja** | ningún modelo mejora el error de la línea base; error mediano de 2,6 puntos anuales | nada por sí solo | decidir entre dos manzanas |
| Escenarios de la ciudad a 2030 (`02`) | **Baja a media** | solo 1 de 3 orígenes quedó dentro del rango; los otros dos, por debajo | poner a prueba una compra en el escenario bajo | tomar el 8,0 % como lo esperado |
| Grupos de comportamiento (`03`) | **Media** | 75 % sigue en su grupo a tres años; el grupo "medio y quieto" es frágil | describir el comportamiento reciente | etiquetar una manzana de forma permanente |
| Oportunidad (`03`) | **Alta** como historia, **baja** como predicción | el 6 % del top 10 % se repite, menos que el 10 % del azar | investigar qué zonas subieron y por qué | anticipar qué zonas van a subir |
| Ranking de potencial 2026-2029 (`potencial_manzanas`) | **Baja** | lift de 1,23× (IC 1,11 a 1,36), algo optimista; el 73 % de las primeras 500 acaba de caer | decidir qué zonas revisar, separando las caídas | priorizar compras o confiar en el orden fino |

## Lo que cambia la lectura del proyecto

1. **El backtest del ranking de potencial estaba inflado; ya se corrigió.** Entrenaba con
   ventanas que aún no terminaban en el origen validado: para validar 2022 usaba la ventana
   2021-2024. Con la regla `fin <= origen` y sin el precio nominal, el lift agregado baja de
   1,74× a **1,23×** (IC por sector 1,11 a 1,36), y el modelo pasa de `hist_gradient` a
   `logit_historia_espacio`. Se eligió por lift después de ver estos resultados, así que la
   cifra es algo optimista. Parte de la caída puede deberse a entrenar con menos ventanas.
2. **El principio del ranking es una lista de caídas.** El 73 % de las primeras 500 cayó a
   menos de la mitad en 2026, contra 2,7 % de la ciudad. Históricamente esas caídas sí
   rebotaron (64 % en el grupo alto, 633 casos), pero 2026 tiene 4,6 veces más que cualquier
   año anterior y eran menos del 3 % del top en el backtest: **el lift no valida esa apuesta**.
   Se marcan con `caida_fuerte_*`, y `puesto_sin_caidas` da el orden sin ellas.
3. **La oportunidad no persiste de un trienio al siguiente.** Correlación de −0,09. Las
   ventanas comparten 2023, lo que empuja la correlación hacia abajo, pero tampoco hay
   señal a favor. Esto también afecta a las "oportunidades limpias" de `informe1.md`,
   sección 2.3: describen lo que pasó, no lo que va a pasar.
4. **Los escenarios de la ciudad han fallado hacia arriba.** El central se pasó por 8,8,
   4,5 y 1,7 puntos en los tres orígenes que se pueden probar.
5. **Los mayores crecimientos pronosticados son rebotes.** Los seis sectores que
   encabezan la tabla del notebook 02 cayeron a 295 200 COP/m² en 2026.

## Dos cosas que se llaman "deriva"

| Término | Qué es | Dónde |
|---|---|---|
| **Deriva de la ciudad** | el crecimiento de la mediana: lo que sube Bogotá entera | Parte A del notebook 02 |
| **Deriva de datos** | cuánto cambia una distribución entre dos momentos | este documento y `src/deriva.py` |
| **Deriva de concepto** | cuánto cambia la relación entre las variables y lo que se predice | notebook 02 y potencial |

## Cómo se mide

### Deriva

| Medida | Fórmula | Lectura |
|---|---|---|
| **PSI** | $\sum_i (a_i - b_i)\ln(a_i/b_i)$, en deciles de la base | menos de 0,10 estable; 0,10 a 0,25 moderada; 0,25 o más fuerte |
| **KS** | $D = \max_x \lvert F_b(x) - F_a(x)\rvert$ | separación máxima entre distribuciones, de 0 a 1 |
| **Wasserstein** | $\frac{1}{s_b}\int_0^1 \lvert F_b^{-1}(u) - F_a^{-1}(u)\rvert du$ | desplazamiento, en desviaciones típicas de la base |
| **Antigüedad del modelo** | error contra 2026 de un modelo entrenado con el precio de un año anterior | qué tan rápido hay que reentrenar |
| **Pendiente por ventana** | $b$ en $\text{crecimiento relativo} = a + b \cdot \text{nivel relativo}$ | si la relación se mantiene en el tiempo |
| **Migración** | $P(\text{grupo después} \mid \text{grupo antes})$ | si una manzana sigue en su grupo |

**Los umbrales del PSI son una convención** que viene del crédito, no algo calibrado para
este mercado. Se reporta el KS como distancia y sin valor p: con 40 mil manzanas, cualquier
diferencia mínima resulta significativa.

### Desempeño e incertidumbre

| Medida | Fórmula | Pregunta | Referencia |
|---|---|---|---|
| **R²** | $1 - \sum(y-\hat{y})^2 / \sum(y-\bar{y})^2$ | ¿cuánta varianza explica? | 0 = la media; negativo = peor que la media |
| **Error relativo mediano** | $\text{mediana}\lvert \hat{P}-P\rvert / P$ | ¿de cuánto es el error típico? | menor es mejor |
| **Spearman** | correlación de los rangos | ¿ordena bien? | 0 = azar |
| **Lift del decil superior** | crecimiento del 10 % señalado menos el de la ciudad | ¿cuánto gana lo señalado? | 0 puntos = sin señal |
| **Lift del top 20 %** | precisión en el top 20 % / prevalencia | ¿concentra los casos positivos? | 1× = sin señal |
| **AUC** | probabilidad de puntuar más alto a un positivo que a un negativo | ¿separa las clases? | 0,5 = azar |
| **Brier skill** | $1 - \text{Brier}_{\text{modelo}} / \text{Brier}_{\text{sin señal}}$ | ¿sirve el puntaje como probabilidad? | menor o igual a 0 = no |
| **IC 95 % por sector** | percentiles 2,5 y 97,5 remuestreando sectores completos | ¿es ruido? | si cruza la referencia, no es concluyente |
| **Intervalo conforme** | $\hat{y} \pm q$, con $q$ cuantil del error en otros pliegues | ¿cuál es el margen de una estimación? | cobertura cercana a lo pedido |
| **Cobertura de escenarios** | fracción de orígenes en que lo observado cayó dentro del rango | ¿contiene el rango lo que pasa? | mientras más alta, mejor |

### Agrupamiento

| Medida | Fórmula | Pregunta | Referencia |
|---|---|---|---|
| **Hopkins** | $\sum u_i / (\sum u_i + \sum w_i)$ | ¿hay algo que agrupar? | comparar con los datos barajados |
| **Estabilidad (ARI)** | índice de Rand ajustado entre dos particiones | ¿se repite la partición? | 1 = igual; 0 = azar |
| **Jaccard por grupo** | $\max_B \lvert A\cap B\rvert / \lvert A\cup B\rvert$ | ¿se repite este grupo? | 0,75 o más estable; menos de 0,60 dudoso |
| **Silueta** | $(b-a)/\max(a,b)$, promedio | ¿están compactos y separados? | de −1 a 1 |
| **Pureza espacial** | fracción de los 8 vecinos en el mismo grupo | ¿dibuja zonas? | $\sum_g p_g^2$ = azar |
| **η²** | varianza entre grupos / varianza total | ¿el grupo explica esta variable? | 0,01 pequeño; 0,06 medio; 0,14 grande |

## Resultados por notebook

### `01_valor_suelo`: nivel del precio

| Métrica | Valor |
|---|---|
| R² en sectores no vistos | 0,787 (IC 0,757 a 0,812) |
| Error relativo mediano | 9,8 % (IC 9,1 % a 10,4 %) |
| Margen del 80 % | −23 % a +30 %; cobertura 80 %, peor pliegue 76 % |
| Margen del 90 % | −34 % a +52 %; cobertura 90 %, peor pliegue 87 % |
| Margen del 90 % por zona | +31 % en la Zona T, +77 % en Usaquén |
| PSI del precio relativo, año contra año | 0,00 a 0,05: **estable** |
| PSI del precio relativo contra 2017 | hasta 0,13: **moderada** |
| Error con un modelo de 1, 3 y 9 años | 11,3 %, 12,2 % y 16,5 %, frente a 9,8 % |

### `02_pronostico`: crecimiento

| Métrica | Valor |
|---|---|
| Modelos que mejoran el MAE de la línea base con 95 % de confianza | 0 de 10 |
| Spearman de la reversión a la media | 0,318 (IC 0,261 a 0,370) |
| Lift del decil superior, reversión | +7,1 puntos (IC +1,9 a +9,9); en otras ventanas +1,5 a +7,8 |
| Acierto de dirección, reversión | 60,3 % (IC 57,5 % a 63,0 %) |
| Error por manzana (p50, p80, p90) | 2,6, 5,9 y 8,0 puntos anuales |
| Pendiente de la reversión por ventana | −0,019 a −0,051; siempre negativa |
| R² fuera de tiempo de la reversión | −0,20 a +0,11 |
| Cobertura de los escenarios | 1 de 3 orígenes |
| PSI de `g2` y `vec_g2` | 2,8 y 3,6 (2020-2023): **fuerte** |
| PSI de `nivel_rel` | 0,01 y 0,09: **estable** |
| PSI de la predicción del ensamble | 0,02: **estable** |
| MAE: línea base, reversión y ensamble encogido | 4,35, 4,29 y 4,27 puntos anuales |
| Pendiente de calibración del ensamble | 0,76 con todas; 0,19 sin el 1 % de predicciones extremas |
| MAE por tramo de precio | unos 8,5 puntos en el más barato; cerca de 3 en los demás |
| Spearman de la reversión dentro de cada tramo | 0,31, 0,09, 0,06, −0,04 y 0,33, de barato a caro |

El ensamble se eligió y se calibró con el mismo periodo con que se evalúa: su R² de 0,135
es optimista.

### `03_clusters`: comportamiento

| Métrica | Valor |
|---|---|
| Hopkins (datos y barajados) | 0,995 y 0,981 |
| Estabilidad (ARI) | 0,55 ± 0,19 |
| Silueta | 0,30 |
| Pureza espacial (real y azar) | 0,86 y 0,44 |
| Jaccard por grupo | 0,74 ("medio y quieto") a 1,00 ("barato, estancado") |
| Permanencia a tres años | 75 % (ARI 0,45) |
| PSI del peso de los grupos | 0,04: **estable** |
| PSI de los rasgos | `tadc_reciente` 0,68 y `tadc_total` 0,33: **fuerte**; `nivel` 0,09 e `inercia` 0,04: **estable** |
| Persistencia de la oportunidad | Spearman −0,09; se repite el 6 % del top 10 % |

### `potencial_manzanas`: ranking

| Métrica | Versión anterior (`hist_gradient`) | Versión actual (`logit_historia_espacio`) |
|---|---:|---:|
| Lift agregado | 1,74× (IC 1,64 a 1,85) | **1,23× (IC 1,11 a 1,36)** |
| Lift por origen (2020, 2021, 2022, 2023) | 1,57, 1,41, 2,60, 1,48 | 1,39, 1,18, 1,14, 1,22 |
| AUC por origen | 0,64, 0,60, 0,76, 0,59 | 0,56, 0,51, 0,50, 0,57 |
| Brier skill por origen | | −0,01, −0,04, −0,04, −0,01 |

| Métrica de la versión actual | Valor |
|---|---|
| PSI de `log_precio_inicio` en 2026 (ya no entra al modelo) | 0,69: **fuerte** |
| PSI de `precio_relativo_ciudad` en 2026 | 0,04: **estable** |
| PSI del puntaje entre 2023 y 2026 | 0,22: **moderada** |
| Top 20 % compartido entre 2023 y 2026 | 51 %; por azar, 20 % |
| Primeras 500 con caída fuerte en 2026 | 73 %; ciudad, 2,7 % |
| Primeras 500 sin caídas | 2,9 M de mediana, en 72 sectores |
| Caídas fuertes que terminaron en el grupo alto | 64 % (de 36 % a 77 % según la ventana); base, 20 % |

## Lo que estas medidas no ven

- **Precios de mercado.** Todo se valida contra el valor de Catastro. Si ese valor se
  aparta del mercado, ningún indicador de aquí lo detecta.
- **Lo local.** Un PSI bajo habla de la distribución entera: el de 2026 es 0,02 y ese año
  2 437 manzanas bajaron de valor.
- **La morfología en el tiempo.** Es una sola foto, así que no tiene deriva medible, y las
  pruebas de antigüedad del modelo salen algo optimistas.
- **El futuro.** Hay pocas ventanas, se solapan entre sí y una tiene el 2022 congelado. Los
  rangos describen lo que se ha visto, no lo que puede pasar.

## Qué revisar cuando salga el dato de 2027

1. Correr los notebooks en orden. Cada uno deja sus tablas en `data/processed/deriva_*.csv`
   o en `potencial_manzanas/outputs/`.
2. **¿Hubo otro congelamiento?** Si más del 80 % de las manzanas no cambia, las variables de
   crecimiento dejan de ser comparables.
3. **¿Algún PSI de variables que pesan pasó de 0,25?** Sobre todo `nivel_rel` y
   `precio_relativo_ciudad`. Si es así, hay que revisar antes de usar el modelo.
4. **¿Sigue negativa la pendiente de la reversión?** Si cambia de signo, se cae la única
   señal firme del pronóstico.
5. **Comparar lo pronosticado con lo observado.** Es la primera validación real del
   pronóstico y del ranking fuera de muestra. Hay que mirar en especial si rebotaron las
   manzanas que cayeron en 2026.

## Dónde está cada cosa

| Archivo | Qué trae |
|---|---|
| `src/deriva.py` | las funciones de PSI, KS y Wasserstein, y los umbrales |
| `data/processed/deriva_01_precio.csv`, `deriva_01_modelo.csv` | deriva anual del precio y antigüedad del modelo |
| `data/processed/deriva_02_variables.csv`, `deriva_02_ventanas.csv`, `deriva_02_escenarios.csv` | variables, reversión por ventana y cobertura de escenarios |
| `data/processed/desempeno_02_modelos.csv`, `desempeno_02_tramos.csv` | desempeño del modelo, global y por tramo de precio |
| `data/processed/deriva_03_rasgos.csv`, `deriva_03_migracion.csv`, `deriva_03_oportunidad.csv` | rasgos, migración entre grupos y persistencia de la oportunidad |
| `potencial_manzanas/outputs/deriva_variables.csv`, `backtest_comparacion_reglas.csv`, `rebote_caidas.csv`, `ranking_caidas.csv` | variables, comparación de reglas de entrenamiento, rebote histórico y caídas en el ranking |
