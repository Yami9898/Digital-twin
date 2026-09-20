"""Operations MySQL relatives aux recettes de cycle."""

from __future__ import annotations

import json
from typing import Any

from app.database.connection import get_connection


def _encode_recipe_data(recipe_data: dict) -> str:
    if not isinstance(recipe_data, dict) or not recipe_data:
        raise ValueError("La recette a enregistrer doit contenir des donnees structurees.")
    return json.dumps(recipe_data, ensure_ascii=False)


def _decode_recipe_data(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if not value:
        raise ValueError("La recette enregistree ne contient pas de donnees JSON.")
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ValueError("Le JSON de la recette doit contenir un objet.")
    return decoded


def test_connection() -> bool:
    """Verifie que MySQL accepte une connexion."""
    connection = get_connection()
    try:
        return connection.is_connected()
    finally:
        connection.close()


def save_recipe(
    name: str,
    recipe_data: dict,
    description: str | None = None,
    cycle_type: str | None = None,
    product_name: str | None = None,
) -> int:
    """Enregistre une nouvelle recette et retourne son identifiant."""
    payload = _encode_recipe_data(recipe_data)
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO recipes
                (name, description, cycle_type, product_name, recipe_data)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, description, cycle_type, product_name, payload),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_all_recipes() -> list[dict[str, Any]]:
    """Retourne les recettes actives disponibles pour le chargement."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, name, version, description, cycle_type, product_name,
                   created_at, updated_at
            FROM recipes
            WHERE is_active = TRUE
            ORDER BY updated_at DESC, name ASC
            """
        )
        return list(cursor.fetchall())
    finally:
        cursor.close()
        connection.close()


def get_recipe_by_id(recipe_id: int) -> dict[str, Any] | None:
    """Retourne une recette active complete, avec son JSON decode."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT id, name, version, description, cycle_type, product_name,
                   recipe_data, created_at, updated_at, is_active
            FROM recipes
            WHERE id = %s AND is_active = TRUE
            """,
            (recipe_id,),
        )
        recipe = cursor.fetchone()
        if recipe is None:
            return None
        recipe["recipe_data"] = _decode_recipe_data(recipe["recipe_data"])
        return recipe
    finally:
        cursor.close()
        connection.close()


def update_recipe(
    recipe_id: int,
    name: str,
    recipe_data: dict,
    description: str | None = None,
    cycle_type: str | None = None,
    product_name: str | None = None,
) -> bool:
    """Met a jour la recette active cible sans modifier son versionnement."""
    payload = _encode_recipe_data(recipe_data)
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE recipes
            SET name = %s, description = %s, cycle_type = %s,
                product_name = %s, recipe_data = %s
            WHERE id = %s AND is_active = TRUE
            """,
            (name, description, cycle_type, product_name, payload, recipe_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def duplicate_recipe(recipe_id: int, new_name: str | None = None) -> int:
    """Duplique une recette existante dans une nouvelle ligne active."""
    source = get_recipe_by_id(recipe_id)
    if source is None:
        raise ValueError("La recette a dupliquer est introuvable.")
    name = (new_name or "").strip() or f"Copie de {source['name']}"
    return save_recipe(
        name,
        source["recipe_data"],
        description=source.get("description"),
        cycle_type=source.get("cycle_type"),
        product_name=source.get("product_name"),
    )


def deactivate_recipe(recipe_id: int) -> bool:
    """Desactive une recette au lieu de supprimer son historique."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE recipes SET is_active = FALSE WHERE id = %s AND is_active = TRUE",
            (recipe_id,),
        )
        connection.commit()
        return cursor.rowcount > 0
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
