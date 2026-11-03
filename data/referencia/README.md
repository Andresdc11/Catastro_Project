# Morfología de referencia

`morfologia_manzanas.csv.gz` es la morfología con la que se calcularon los resultados
publicados: una fila por manzana, 40 581 manzanas.

Está en el repositorio porque el servicio de Catastro solo entrega la versión vigente de
las construcciones, y con ella algunos resultados cambian. Así se pueden reproducir las
cifras publicadas sin el archivo original de 1,8 GB.

| | |
|---|---|
| **Origen** | capa de construcciones de la Unidad Administrativa Especial de Catastro Distrital (UAECD), en `Construcciones.geojson` |
| **Registros de origen** | 2 401 061 construcciones |
| **Fecha** | el archivo de origen no declara su fecha de corte; se guardó el 2026-08-30 |
| **Cómo se generó** | `src/morfologia.py`, que documenta cada columna |

Es un dato derivado de Catastro, agregado por manzana. No contiene geometrías ni
información de predios individuales.
