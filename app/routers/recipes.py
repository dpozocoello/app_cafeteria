"""
Router: Recetas CRUD
Endpoints para gestión completa de recetas (BOM).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.inventory import Recipe, Product
from ..schemas import RecipeCreate

router = APIRouter(prefix="/api/recipes", tags=["Recetas"])


@router.get("/")
def list_recipes(db: Session = Depends(get_db)):
    """Retorna todas las recetas agrupadas por producto."""
    recipes = db.query(Recipe).all()
    result = {}
    for r in recipes:
        product = db.get(Product, r.product_id)
        ingredient = db.get(Product, r.ingredient_id)
        key = str(r.product_id)
        if key not in result:
            result[key] = {
                "product_id": r.product_id,
                "product_name": product.name if product else "?",
                "ingredients": []
            }
        result[key]["ingredients"].append({
            "recipe_id": r.id,
            "ingredient_id": r.ingredient_id,
            "ingredient_name": ingredient.name if ingredient else "?",
            "ingredient_unit": ingredient.unit if ingredient else "",
            "quantity": float(r.quantity)
        })
    return list(result.values())


@router.post("/", status_code=201)
def create_recipe(data: RecipeCreate, db: Session = Depends(get_db)):
    """Reemplaza la receta completa del producto."""
    # Eliminar líneas previas del producto
    db.query(Recipe).filter_by(product_id=data.product_id).delete()

    new_lines = []
    for line in data.ingredients:
        recipe = Recipe(
            product_id=data.product_id,
            ingredient_id=line.ingredient_id,
            quantity=line.quantity
        )
        db.add(recipe)
        new_lines.append(recipe)

    db.commit()
    return {"message": "Receta guardada", "lines_saved": len(new_lines)}


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe_line(recipe_id: int, db: Session = Depends(get_db)):
    """Elimina una línea individual de receta."""
    line = db.get(Recipe, recipe_id)
    if not line:
        raise HTTPException(status_code=404, detail="Línea de receta no encontrada")
    db.delete(line)
    db.commit()
