# Informe 1 · Valor del suelo en Bogotá

**Nomenclatura, análisis de inversión y casos de detrimento por manzana**

Fecha: 25 de octubre de 2026 · Fuente: valor de referencia del m² de terreno de
Catastro Bogotá, serie 2017-2026 · Base: notebooks `01_valor_suelo`,
`02_pronostico` y `03_clusters`, y los archivos de `data/processed/`.

> El valor de referencia (`V_REF`) es un **valor administrativo** que Catastro
> actualiza por zonas y por turnos; no es un precio de transacción. Todo lo que
> sigue describe ese valor. Antes de comprar, hay que contrastarlo con ofertas y
> transacciones reales.

---

## Resumen

1. **La ciudad sube 8,9 % anual nominal** (mediana de 1,2 M/m² en 2017 a 2,6 M en
   2026). Hacia 2030 iría a 3,8 M/m², entre 3,3 M y 4,8 M según el escenario.
2. **La única señal firme para elegir dónde comprar es la reversión a la media:**
   lo barato crece más rápido en porcentaje. Ningún modelo le gana con 95 % de
   confianza a "todas las manzanas crecen como la ciudad".
3. **Hay oportunidades limpias en los tres tramos de precio:** sectores que crecen
   9 a 12 puntos anuales por encima de lo esperado para su precio, sin saltos ni
   años hundidos (sección 2.3).
4. **Las "mejores oportunidades" del notebook 03 no lo son.** Las tres primeras, en
   el borde norte de Usaquén, salen infladas por un 2023 hundido.
5. **2026 fue un año de caídas:** 2 437 manzanas bajaron de valor, 784 más de un
   20 % y 496 más de la mitad. El caso más fuerte es Usme, donde 12 sectores pasaron
   de 0,8-1,2 M a 295 k/m² en un solo año.
6. **Los estratos altos pierden en términos reales:** el 72 % de las manzanas de
   estrato 6 creció menos que la inflación entre 2017 y 2026.

---

## 1. Nomenclatura

### 1.1 Identificadores y unidades

| Término | Qué es | Ejemplo |
|---|---|---|
| `MANCODIGO` | código catastral de la **manzana**, 9 dígitos: los 6 primeros son el sector y los 3 últimos la manzana dentro del sector | `008540020` |
| `sector` | **sector catastral**, 6 dígitos. Su nombre casi siempre es el del barrio | `008540` = La Estrellita I |
| `barrio` | nombre del sector catastral (lo descarga `src/zonas.py`) | Santa Cecilia Puente Norte |
| `localidad` | una de las 20 localidades del Distrito, asignada por cruce espacial | Usaquén |
| `V_REF` / `cop_m2` | valor de referencia del m² de terreno, en pesos corrientes | 2 650 000 |
| `P_t` | `V_REF` de la manzana en el año *t* (mediana si hay varios registros) | P₂₀₂₆ |
| k / M | miles / millones de pesos por m² | 295 k = 295 000 COP/m² |
| σ (sigma) | desviación típica; "+2 σ" es dos desviaciones por encima del promedio de la ciudad | — |

**2022 es un año congelado:** Catastro no actualizó el valor de ninguna manzana
(el 100 % quedó igual que en 2021). Por eso se excluye de las medidas de
volatilidad, inercia y salto.

### 1.2 Variables de comportamiento de cada manzana

Todas se calculan sobre el logaritmo base 10 del precio. El cambio de un año es
`g_t = log10(P_t) − log10(P_t−1)`.

| Variable | Fórmula | Qué mide | Cómo leerla |
|---|---|---|---|
| `nivel` | log10(P₂₀₂₆) | el precio de hoy | 10^nivel = pesos/m². 6,45 ≈ 2,8 M |
| **TADC** (`tadc_total`) | (P₂₀₂₆ / P₂₀₁₇)^(1/9) − 1 | **tasa anual de crecimiento**, 2017-2026 | 8 % = el valor crece 8 % cada año en promedio compuesto |
| `tadc_reciente` | (P₂₀₂₆ / P₂₀₂₃)^(1/3) − 1 | la misma tasa en el último trienio | si supera a la total, la manzana acelera |
| `volatilidad` | desviación típica de los 8 `g_t` | qué tan parejos son los cambios anuales | 0,03 es lo típico; 0,3 son sacudidas |
| `inercia` | (años con `g_t` = 0) / 8 | fracción de años en que Catastro no movió el valor | 0,25 = 2 de 8 años quieto |
| `salto_max` | max `g_t` | la mayor alza de un solo año | el valor se multiplicó por 10^salto_max |
| `vs_ciudad` | TADC manzana − TADC ciudad | valorización frente a la mediana de Bogotá | +3 = gana 3 puntos anuales a la ciudad |
| `pron_relativo` / `crec_relativo_pct` | término relativo del notebook 02 | cuánto espera el pronóstico que crezca por encima (+) o por debajo (−) de la ciudad | puntos % anuales |
| `nivel_inicio` | log10(P₂₀₂₃) | precio al inicio del último trienio | se usa para calcular la oportunidad |

Ejemplo de TADC: de 1,0 M en 2017 a 2,0 M en 2026 es 2^(1/9) − 1 ≈ 8 % anual. La
TADC solo mira el primer y el último año; por eso va acompañada de la volatilidad
y del salto máximo.

### 1.3 Medidas derivadas

| Medida | Fórmula | Para qué |
|---|---|---|
| **oportunidad** | `tadc_reciente − f(nivel_inicio)`, con *f* una regresión isotónica decreciente | crecimiento **por encima de lo esperado para su precio**. Descuenta que lo barato sube más rápido |
| **fuerza** de una atípica | max \|z\| entre sus variables | cuántas desviaciones típicas se aparta en su rasgo más extremo. 3 ya es raro |
| **detectores** | ruido de DBSCAN · verosimilitud baja en la mezcla gaussiana · lejanía al centroide de K-Means | una manzana es **atípica** si la marcan 2 o 3 |
| **zona** | sector catastral con 3 o más atípicas | agrupa atípicas que probablemente comparten causa |
| **η²** | varianza entre grupos / varianza total | qué fracción de una variable explica el grupo. 0,06 es efecto medio y 0,14 grande |
| **escenarios de deriva** | trienio más flojo (4,3 %), mediana de los trienios (8,0 %), trienio más fuerte (14,5 %) | crecimiento anual nominal de la ciudad hacia 2030 |
| `cop_m2_2030_*` | P₂₀₂₆ × (1 + deriva)⁴ × (1 + relativo)⁴ | pronóstico 2030 por escenario: bajo, central y alto |

### 1.4 Los cinco grupos de comportamiento

Salen de K-Means usando **solo** el comportamiento del precio, sin ubicación ni
estrato. El nombre es una ayuda de lectura.

| Grupo | Manzanas | Precio mediano | TADC 2017-26 | TADC 2023-26 | Lectura |
|---|---:|---:|---:|---:|---|
| **0 · caro, al ritmo de la ciudad** | 21 848 (58 %) | 3,4 M | 8,2 % | 7,5 % | suelo consolidado y predecible |
| **4 · barato, al ritmo de la ciudad** | 10 982 (29 %) | 1,5 M | 11,0 % | 10,1 % | barrio popular consolidado: más valorización sin más riesgo |
| **1 · medio y quieto** | 3 253 (9 %) | 2,7 M | 6,2 % | 6,6 % | Catastro le actualiza poco el valor; puede ir detrás del mercado |
| **3 · barato, acelerando e inestable** | 737 (2 %) | 1,5 M | 20,7 % | 11,5 % | crece a saltos: hay que verificar cada salto |
| **2 · barato, estancado e inestable** | 608 (2 %) | 295 k | 1,0 % | −25,0 % | periferia de estrato 1; el único grupo que cae |

### 1.5 Patrones de las manzanas atípicas

| Patrón | Manzanas | Qué le pasó a la serie |
|---|---:|---|
| **bache** | 214 | un año hundido entre dos normales: cae y al año siguiente rebota |
| **salto** | 83 | el valor se multiplica de golpe en un año |
| **alza** | 77 | crecimiento sostenido muy por encima de la ciudad |
| **caída** | 52 | pierde valor de forma sostenida |
| **quieta** | 44 | muchos años sin cambio de valor |
| **pronóstico** | 23 | atípica por lo que espera el modelo, no por su historia |
| **precio** | 1 | precio extremo para la ciudad |

### 1.6 Archivos de consulta

| Archivo | Contenido |
|---|---|
| `data/processed/clusters_manzanas.csv.gz` | las 37 428 manzanas con sus variables, grupo y oportunidad |
| `data/processed/pronostico_manzanas.csv.gz` | precio 2026 y pronóstico 2030 en tres escenarios |
| `data/processed/atipicas_manzanas.csv` | las 494 atípicas con patrón, porqué y enlace a Google Maps |
| `data/processed/atipicas_zonas.csv` | los 224 sectores con atípicas |
| `data/processed/atipicas_mapa.html` | mapa interactivo con localidades, patrones y zonas |
| `potencial_manzanas/outputs/potencial_2026_2029.csv.gz` | ranking experimental de potencial 2026-2029 |

---

## 2. Análisis de inversión

### 2.1 El mercado en conjunto

- **Crecimiento de la ciudad:** 8,9 % anual nominal entre 2017 y 2026. El ritmo se
  frenó: 16 % en 2018 y 2020, y entre 5 % y 10 % desde 2023.
- **Pronóstico a 2030:** la mediana iría de 2,8 M a **3,8 M/m²** en el escenario
  central (8 % anual), con un rango de 3,3 M a 4,8 M. **La incertidumbre grande no
  está en la manzana sino en la ciudad:** 10 puntos anuales entre escenarios,
  contra 2,7 de error del modelo por manzana.
- **Qué explica el precio:** sobre todo la ubicación, con el corredor del norte (Zona
  T, Calle 100, Usaquén) y Salitre. Le siguen la morfología y el estrato. La
  distancia a la Plaza de Bolívar no explica nada (ρ = −0,05).
- **Qué explica el crecimiento:** casi solo el precio de partida. Lo barato crece
  más rápido en porcentaje (ρ = −0,44). El decil que señala la reversión a la
  media creció 7,1 puntos anuales más que la ciudad, y acierta la dirección en el
  60 % de los casos.

### 2.2 Qué grupo según el perfil del comprador

| Perfil | Grupo | Por qué |
|---|---|---|
| Conservador: preservar valor | **0 · caro, al ritmo de la ciudad** | baja volatilidad. Ojo: en los estratos 5 y 6 crece por debajo de la inflación (sección 3.3) |
| Valorización con riesgo moderado | **4 · barato, al ritmo de la ciudad** | 10-11 % anual con la misma estabilidad del grupo 0 |
| Buscar valor no reconocido | **1 · medio y quieto** | Catastro le actualiza poco el valor, que puede ir detrás del mercado. Requiere comparar con ofertas reales |
| Especulativo | **3 · acelerando e inestable** | crece a saltos. Cada salto debe verificarse (norma, obra, englobe) |
| Evitar sin estudio | **2 · estancado e inestable** | cae 25 % anual desde 2023. El rebote del pronóstico es estadístico, no observado |

### 2.3 Oportunidades limpias

Los sectores con mayor **oportunidad** (crecimiento 2023-2026 por encima del
esperado para su precio) pasan por tres filtros:

- se excluyen las manzanas atípicas;
- solo se toman manzanas con volatilidad menor a 0,06, que crecen parejo, sin saltos
  ni años hundidos;
- solo entran sectores con al menos 15 manzanas así.

Están separados por tramo de precio para no comparar barrios populares con el norte.

**Menos de 2 M/m²**

| Sector | Barrio | Localidad | Precio 2026 | Estrato | TADC 17-26 | TADC 23-26 | Oportunidad | 2030 central |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 001420 | El Playón | Rafael Uribe Uribe | 1,95 M | 1 | 15,1 % | 21,0 % | +11,7 | 2,66 M |
| 002502 | Millán | Ciudad Bolívar | 1,73 M | 2 | 9,7 % | 20,1 % | +10,7 | 2,37 M |
| 002517 | Lucero del Sur | Ciudad Bolívar | 1,73 M | 2 | 12,5 % | 20,1 % | +10,7 | 2,36 M |
| 002523 | La Alameda | Ciudad Bolívar | 1,73 M | 2 | 11,5 % | 20,1 % | +10,7 | 2,36 M |
| 002554 | Gibraltar Sur | Ciudad Bolívar | 1,60 M | 1 | 11,2 % | 19,0 % | +9,8 | 2,16 M |
| 002504 | Compartir | Ciudad Bolívar | 1,22 M | 1 | 11,7 % | 18,5 % | +9,3 | 1,66 M |

**Entre 2 M y 4 M/m²**

| Sector | Barrio | Localidad | Precio 2026 | Estrato | TADC 17-26 | TADC 23-26 | Oportunidad | 2030 central |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 004562 | Llano Grande | Kennedy | 3,05 M | 2 | 13,2 % | 20,3 % | +11,0 | 4,16 M |
| 006517 | María Paz | Kennedy | 3,05 M | 2 | 13,2 % | 20,3 % | +11,0 | 4,18 M |
| 004535 | Class | Kennedy | 2,90 M | 2 | 11,4 % | 18,6 % | +9,4 | 3,91 M |
| 004625 | El Remanso I | Bosa | 2,14 M | 2 | 10,1 % | 18,1 % | +8,9 | 2,90 M |
| 001418 | Marruecos | Rafael Uribe Uribe | 2,60 M | 2 | 12,5 % | 17,6 % | +8,5 | 3,54 M |
| 001421 | Diana Turbay | Rafael Uribe Uribe | 2,60 M | 2 | 11,8 % | 17,6 % | +8,5 | 3,54 M |

**Más de 4 M/m²**

| Sector | Barrio | Localidad | Precio 2026 | Estrato | TADC 17-26 | TADC 23-26 | Oportunidad | 2030 central |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 008526 | El Vervenal | Usaquén | 4,10 M | 3 | 11,4 % | 21,3 % | +11,9 | 5,56 M |
| 008528 | San Antonio Noroccidental | Usaquén | 4,10 M | 2 | 12,2 % | 21,3 % | +11,9 | 5,54 M |
| 006514 | Vergel Occidental | Kennedy | 5,03 M | 2 | 10,8 % | 19,1 % | +10,5 | 6,75 M |
| 008212 | Marly | Chapinero | 6,30 M | 4 | 9,0 % | 16,4 % | +9,9 | 8,32 M |
| 008213 | Chapinero Central | Chapinero | 6,30 M | 3 | 9,4 % | 16,4 % | +9,9 | 8,46 M |
| 009220 | Lago de Suba | Suba | 4,20 M | 2 | 11,3 % | 18,4 % | +9,3 | 5,69 M |

Oportunidad en puntos porcentuales anuales. "2030 central" es la mediana del
sector con la ciudad creciendo 8 % anual.

**Cómo leer estas tablas:**

- **Son sectores que se valorizaron por encima de sus pares, sin señales de error
  administrativo.** Eso es una pista, no una garantía. El notebook 02 mostró que
  lo que subió no sigue subiendo por sí solo (el *momentum* fue el peor modelo).
- **El pronóstico 2030 de todos ronda el 8 % anual,** el de la ciudad. El modelo no
  les proyecta la oportunidad pasada hacia adelante. Si la valorización continúa,
  será por algo que el modelo no ve: norma, obras o demanda.
- **Varios sectores comparten precio y crecimiento idénticos,** como Millán, Lucero
  del Sur y La Alameda, o Llano Grande y María Paz. Catastro les asigna el mismo
  valor por zona homogénea, así que se mueven juntos.
- **El caso de Chapinero es distinto:** Marly y Chapinero Central son de los pocos
  sectores caros que crecen por encima de sus pares de precio.

### 2.4 Falsas oportunidades

| Sector | Barrio | Oportunidad aparente | Por qué no es real |
|---|---|---:|---|
| 008543 | Santa Cecilia Puente Norte (Usaquén) | +58,9 | en 2023 el valor cayó a ÷6 y en 2024 rebotó ×6,7. Medida desde ese 2023 hundido, la tasa se infla |
| 008504 | La Cita (Usaquén) | +54,2 | el mismo bache de 2023 |
| 008540 | La Estrellita I (Usaquén) | +53,8 | el mismo bache de 2023: 38 de sus 45 manzanas son atípicas |

En total, **214 de las 494 atípicas tienen un año hundido.** Cualquier tasa medida
desde ese año sale exagerada. Hay que mirar la serie completa antes de creer en un
crecimiento alto.

Sobre el **ranking de potencial** (`potencial_manzanas/`): entre sus primeras 200
manzanas aparecen algunas de Usme que acaban de caer a 295 k en 2026 (sección
3.2). El modelo las ve baratas y les asigna rebote, que es la misma reversión a la
media. No deben leerse como recomendación sin revisar por qué cayeron.

### 2.5 Lista de verificación antes de comprar

1. **Revisar la serie completa de la manzana** en `atipicas_manzanas.csv` o en el
   mapa, no solo la tasa. ¿Hay un bache o un salto?
2. **Confirmar la norma urbanística** (POT, tratamiento, edificabilidad) en la
   curaduría o en SINUPOT. Este análisis no la incluye.
3. **Comparar el valor de referencia con ofertas y transacciones reales** de la
   zona. El valor de referencia es administrativo.
4. **Pedir el certificado catastral** y verificar englobes o cambios de destino.
5. **Visitar el sitio:** obras, vías y cambios de uso que todavía no están en los
   datos.

---

## 3. Casos de detrimento

### 3.1 Tres formas de perder valor

| Tipo | Definición | Manzanas (de 37 428) |
|---|---|---:|
| **Nominal 2017-2026** | el valor de 2026 es menor que el de 2017 | 405 (1,1 %) |
| **Nominal reciente** | el valor de 2026 es menor que el de 2023 | 1 118 (3,0 %) |
| **Real** | la TADC 2017-2026 queda por debajo de la inflación (≈ 5,9 % anual, promedio del IPC del DANE 2018-2024) | 5 428 (14,5 %) |
| **Caída de un año** | el valor de 2026 es menor que el de 2025 | 2 437 (6,5 %) |

La cifra del IPC es una referencia aproximada para separar crecimiento nominal de
real; conviene reemplazarla por la serie oficial del DANE.

### 3.2 La caída de 2026

2026 es el año con más caídas de la serie, el doble que 2023, el año del bache de
Usaquén:

| Año | Manzanas que bajan | Bajan más de 20 % |
|---|---:|---:|
| 2019 | 758 | 367 |
| 2020 | 762 | 282 |
| 2023 | 1 323 | 511 |
| **2026** | **2 437** | **784** |

De las 784 manzanas que perdieron más del 20 %, **411 están en Usme**, 99 en
Rafael Uribe Uribe y 76 en Suba. Por estrato, 414 son de estrato 1 y 153 de
estrato 2.

**Los sectores más afectados en 2026**

| Sector | Barrio | Localidad | Manzanas que caen | Valor 2025 | Valor 2026 | Cambio |
|---|---|---|---:|---:|---:|---:|
| 002538 | Usminia | Usme | 67 | 800 k | 295 k | −63 % |
| 002594 | Villa Israel | Usme | 60 | 800 k | 295 k | −63 % |
| 002571 | Antonio José de Sucre | Usme | 47 | 800 k | 295 k | −63 % |
| 002576 | Serranías I | Usme | 47 | 800 k | 295 k | −63 % |
| 002543 | Comuneros | Usme | 46 | 1,20 M | 295 k | −75 % |
| 002611 | Charalá | Usme | 43 | 1,20 M | 295 k | −75 % |
| 002302 | Santander Sur | Antonio Nariño | 24 | 3,10 M | 848 k | −73 % |
| 009129 | Villa del Prado | Suba | 60 | 2,66 M | 2,00 M | −25 % |
| 001412 | Granjas San Pablo | Rafael Uribe Uribe | 42 | 2,00 M | 1,35 M | −32 % |
| 001417 | Los Molinos | Rafael Uribe Uribe | 18 | 2,75 M | 1,95 M | −29 % |
| 008105 | La Macarena | Santa Fe | 13 | 3,96 M | 2,98 M | −25 % |
| 004627 | Galán | Kennedy | 9 | 2,07 M | 846 k | −59 % |

**Caso Usme.** Doce sectores (Usminia, Villa Israel, Comuneros, Charalá,
Serranías, La Orquídea, La Esperanza, Desarrollo Brazuelos y otros) terminan en
**exactamente 295 200 COP/m²**. Venían de crecer de forma sostenida. Comuneros y
Charalá, por ejemplo, pasaron de 550 k en 2017 a 1,2 M en 2025, y en 2026 caen a
la cuarta parte. Que todos queden en el mismo valor apunta a una **reasignación de
zona homogénea** o a un cambio de clasificación del suelo por parte de Catastro,
más que a un desplome de mercado. Son estos sectores los que forman el grupo 2
("estancado e inestable"), y casi todos (98-100 %) perdieron valor desde 2023.

**Caso Santander Sur (Antonio Nariño).** De 1,2 M en 2017 subió a 3,1 M en 2025 y
cayó a 848 k en 2026 (−73 %), con estrato 3. Una caída de esa magnitud en un barrio
consolidado y central es casi seguro administrativa, y merece revisión directa.

**Caso Villa del Prado (Suba) y La Macarena (Santa Fe).** Son caídas moderadas, de
25 %, en barrios de estrato 4. Villa del Prado vuelve en 2026 al mismo valor de
2017 (2,0 M): su TADC de diez años es 0 %. La Macarena venía de 1,7 M a 3,96 M y
retrocede a 3,03 M.

**Cómo leer estas caídas:**

- **Puede ser otro bache.** Un año hundido como el de Usaquén en 2023, que se
  corrigió al año siguiente. Si es así, el valor de 2027 lo dirá.
- **El pronóstico les da +11,5 % anual,** frente a 8 % de la ciudad. Es reversión a
  la media, no una señal observada.
- **Para un comprador,** un valor de referencia recién caído puede abaratar el
  avalúo y el predial, pero también señalar un cambio de norma o de clasificación
  que limite el uso del suelo. Hay que averiguar la causa antes de leerlo como
  ganga.

### 3.3 Detrimento real en los estratos altos

El otro detrimento es silencioso: **manzanas que suben en pesos pero pierden contra
la inflación**. Se concentra arriba.

| Estrato | TADC mediana 2017-26 | Manzanas por debajo de la inflación |
|---|---:|---:|
| 1 | 10,5 % | 11,6 % |
| 2 | 9,5 % | 6,7 % |
| 3 | 8,3 % | 12,0 % |
| 4 | 6,6 % | 39,3 % |
| 5 | 6,1 % | 45,9 % |
| **6** | **4,6 %** | **72,2 %** |

Por localidad, las de mayor proporción por debajo de la inflación son **Usaquén
(53 %)** y **Chapinero (44 %)**.

**Sectores caros que pierden en términos reales**

| Sector | Barrio | Localidad | Estrato | 2017 | 2025 | 2026 | TADC 17-26 |
|---|---|---|---:|---:|---:|---:|---:|
| 008309 | La Cabrera | Chapinero | 6 | 7,20 M | 9,00 M | 8,06 M | 1,3 % |
| 008202 | Emaús | Chapinero | 5-6 | 4,80 M | 7,55 M | 5,80 M | 1,4 % |
| 008203 | Las Acacias | Chapinero | 6 | 4,80 M | 5,70 M | 5,10 M | 1,5 % |

Son barrios caros que crecieron poco durante nueve años y además bajaron en 2026.
**Para quien invierte en suelo de estrato 5 y 6,** el valor de referencia apenas
preservó el capital nominal y perdió poder adquisitivo. Es la otra cara de la
reversión a la media: lo caro crece menos.

### 3.4 Atípicas de caída sostenida

Además de la caída de 2026, el notebook 03 identifica 52 atípicas con patrón de
**caída** sostenida. Entre las zonas con más casos:

- **Diana Turbay Arrayanes** (Rafael Uribe Uribe)
- **México** (Ciudad Bolívar)
- **Charalá** (Usme)

Pierden entre 39 % y 68 % anual desde 2023 y valen entre 50 k y 290 k/m². El
detalle está en `atipicas_zonas.csv` (columna `que_paso`) y en el mapa interactivo,
con el patrón **caída** en azul.

---

## 4. Limitaciones

- **El valor de referencia es administrativo.** Las actualizaciones por turnos, el
  año congelado (2022) y los baches hacen que parte de lo que se ve sea el
  calendario de Catastro, no el mercado.
- **Faltan la norma urbanística, las licencias y las transacciones.** Son
  justamente lo que explicaría saltos y caídas.
- **El pronóstico por manzana es débil.** Sirve para ordenar, no para tasar. La
  incertidumbre dominante es la de la ciudad entera.
- **El umbral de inflación (5,9 %) es aproximado.** Las cifras de detrimento real
  cambian si se usa la serie oficial del IPC año por año.

## 5. Próximos pasos sugeridos

1. **Medir la TADC reciente con una base robusta,** por ejemplo la mediana 2021-2023,
   para que un año hundido no infle la oportunidad.
2. **Marcar en el pronóstico y en el ranking de potencial** las manzanas con caída
   de 2026 de más del 50 %, hasta saber si es un bache.
3. **Volver a correr todo cuando salga el valor de 2027.** Eso dirá si la caída de
   2026 se revierte, como la de 2023.
4. **Incorporar el IPC oficial** para reportar el crecimiento real por manzana.
