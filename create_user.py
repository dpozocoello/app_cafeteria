from app.database import SessionLocal
from app.models.core import User, Role
from app.services.auth_service import hash_password

def create_user():
    db = SessionLocal()
    try:
        role = db.query(Role).filter_by(name="WAITER").first()
        if not role:
            role = Role(name="WAITER", description="Mesero")
            db.add(role)
            db.commit()
            db.refresh(role)

        user = db.query(User).filter_by(username="mesero1").first()
        if user:
            print("Actualizando contraseña de mesero1...")
            user.password_hash = hash_password("mesero123")
            user.role_id = role.id
        else:
            print("Creando usuario mesero1...")
            user = User(
                username="mesero1",
                password_hash=hash_password("mesero123"),
                full_name="Mesero de Prueba",
                role_id=role.id,
                branch_id=1,
                is_active=True
            )
            db.add(user)
        db.commit()
        print("Usuario mesero1 configurado exitosamente.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_user()
