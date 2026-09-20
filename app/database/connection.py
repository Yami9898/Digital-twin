"""Configuration et creation des connexions MySQL."""

from __future__ import annotations

import os
from typing import Any

try:
    import mysql.connector
except ImportError:  # pragma: no cover - depend de l'environnement utilisateur
    mysql = None  # type: ignore[assignment]


class DatabaseConnectionError(RuntimeError):
    """Erreur explicite lorsque le connecteur ou MySQL est indisponible."""


def get_database_config() -> dict[str, Any]:
    """Retourne la configuration MySQL, surchargeable par variables d'environnement."""
    try:
        port = int(os.getenv("DB_PORT", "8889"))
    except ValueError as exc:
        raise DatabaseConnectionError("DB_PORT doit etre un numero de port valide.") from exc
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": port,
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "database": os.getenv("DB_NAME", "digital_twin_eto"),
    }


def get_connection():
    """Ouvre une connexion MySQL vers la base configuree."""
    if mysql is None:
        raise DatabaseConnectionError(
            "Le module mysql-connector-python n'est pas installe."
        )
    try:
        return mysql.connector.connect(**get_database_config())
    except mysql.connector.Error as exc:
        raise DatabaseConnectionError(
            "Connexion a la base de donnees impossible. "
            "Verifiez que MySQL/MAMP est lance."
        ) from exc
