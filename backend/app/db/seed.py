from app.db.session import SessionLocal
from app.services.auth_service import auth_service


def seed():
    db = SessionLocal()
    try:
        result = auth_service.seed_demo_data(db)
        print(f"Successfully seeded database: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
