"""
Quick way to get a test employee in your local DB so you can hit /verify
without manually POSTing to /employees first every time.

Run with:  python -m scripts.seed_demo_data
"""
from app.database import Base, engine, SessionLocal
from app.models import Employee


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Employee).filter(Employee.email == "demo.employee@intuitive.ai").first()
        if existing:
            print(f"Demo employee already exists: id={existing.id}")
            return
        employee = Employee(name="Demo Employee", email="demo.employee@intuitive.ai")
        db.add(employee)
        db.commit()
        db.refresh(employee)
        print(f"Created demo employee: id={employee.id}, name={employee.name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
