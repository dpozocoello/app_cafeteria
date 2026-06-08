import os
import sys

# Ensure we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import User
from app.utils.security import get_password_hash

def create_test_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "mesero1").first()
        if user:
            print("El usuario mesero1 ya existe. Actualizando contraseña...")
            user.hashed_password = get_password_hash("mesero123")
        else:
            print("Creando usuario mesero1...")
            new_user = User(
                username="mesero1",
                hashed_password=get_password_hash("mesero123"),
                full_name="Mesero de Prueba",
                role="WAITER",
                branch_id=1,
                is_active=True
            )
            db.add(new_user)
        
        db.commit()
        print("Usuario mesero1 configurado exitosamente.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()
