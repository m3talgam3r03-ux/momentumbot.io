"""Classificatore dei messaggi.

Al passo 1 contiene solo la normalizzazione del testo e il riconoscimento dei numeri.
Le regole di classificazione arrivano al passo 3, dopo il catalogo dei formati reali.
"""

from momentum_master.classifier.normalize import normalize_text
from momentum_master.classifier.numbers import NumberToken, extract_numbers, interpret_number

__all__ = ["NumberToken", "extract_numbers", "interpret_number", "normalize_text"]
