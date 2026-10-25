"""Genera el ranking experimental de valorización por manzana."""
import argparse

from src.pipeline import ejecutar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizonte", type=int, default=3,
                        help="años por ventana de valorización (por defecto: 3)")
    parser.add_argument("--fraccion-alta", type=float, default=0.20,
                        help="fracción superior etiquetada como oportunidad (0-1)")
    args = parser.parse_args()
    ejecutar(horizonte=args.horizonte, fraccion_alta=args.fraccion_alta)


if __name__ == "__main__":
    main()
