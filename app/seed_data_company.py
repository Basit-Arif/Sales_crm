from database import SessionLocal
from models.models import Company, SalesRep

def seed_company_and_sales_rep():
    db = SessionLocal()

    try:
        # Create company
        company = Company(
            name="PowerPlus",
            messenger_page_id="245737865859808",
            instagram_page_id=None
        )
        db.add(company)
        db.flush()  # Get company.id before committing

        # Create sales rep assigned to the company
        sales_rep = SalesRep(
            code="YASEEN001",
            name="Yaseen Arif",
            phone_number="03009266997",
            company_id=company.id
        )
        db.add(sales_rep)

        db.commit()
        print("✅ Seed successful: PowerPlus + Yaseen Arif")
    except Exception as e:
        db.rollback()
        print("❌ Error:", str(e))
    finally:
        db.close()

if __name__ == "__main__":
    seed_company_and_sales_rep()
