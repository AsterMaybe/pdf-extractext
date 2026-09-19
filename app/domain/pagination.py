"""
Objetos de valor (VO) para consultas de datos.

`PageQuery` encapsula los parámetros de paginación en una sola entidad de
dominio, evitando obsesión por primitivas y permitiendo extender la consulta
(filtros, orden, cursores) sin romper firmas (OCP).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PageQuery:
    """Parámetros de paginación de una consulta de listado."""

    skip: int = 0
    limit: int = 100