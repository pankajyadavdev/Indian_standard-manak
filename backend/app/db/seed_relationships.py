from app.db.session import SessionLocal
from app.models.standard import Standard, StandardVersion, StandardReference

def seed_extended_relationships():
    db = SessionLocal()
    try:
        print("Seeding all 7 standard relationship types...")
        
        # Helper to get or create standard
        def get_or_create(code: str, title: str, category: str, scope: str):
            std = db.query(Standard).filter(Standard.standard_code == code).first()
            if not std:
                std = Standard(
                    standard_code=code,
                    title=title,
                    category=category,
                    status="active",
                    scope=scope
                )
                db.add(std)
                db.flush()
                v = StandardVersion(
                    standard_id=std.id,
                    year=2020,
                    version_label=f"{code}:2020",
                    is_current=True
                )
                db.add(v)
                db.flush()
            return std

        # Ensure standards exist
        is456 = db.query(Standard).filter(Standard.standard_code == "IS 456").first()
        is1786 = db.query(Standard).filter(Standard.standard_code == "IS 1786").first()
        is732 = db.query(Standard).filter(Standard.standard_code == "IS 732").first()
        is3043 = db.query(Standard).filter(Standard.standard_code == "IS 3043").first()
        is2062 = db.query(Standard).filter(Standard.standard_code == "IS 2062").first()

        is1608 = get_or_create("IS 1608", "Metallic Materials - Tensile Testing at Ambient Temperature", "Metallurgy", "Specifies the method for tensile testing of metallic materials.")
        is269 = get_or_create("IS 269", "Ordinary Portland Cement - Specification", "Civil", "Covers the manufacture and chemical and physical requirements of ordinary Portland cement.")
        is1950 = get_or_create("IS 1950", "Glossary of Terms Relating to Concrete and Concrete Aggregates", "Civil", "Provides definitions of terms used in concrete technology and construction.")

        # Seed relationships
        relationships = [
            (is456, is1786, "normative", "Clause 5.6.1", "Reinforcement steel shall conform to IS 1786."),
            (is1786, is1608, "test_method", "Clause 8.1", "Tensile test shall be conducted in accordance with IS 1608."),
            (is732, is3043, "safety", "Clause 8.4", "Protective earthing and bonding shall satisfy IS 3043."),
            (is456, is732, "installation", "Clause 12.3", "Embedded electrical conduit installation shall comply with IS 732."),
            (is456, is269, "material", "Clause 5.1", "Cement used shall conform to IS 269 for ordinary Portland cement."),
            (is456, is1950, "terminology", "Clause 3.1", "Terminology relating to concrete shall be as defined in IS 1950."),
            (is2062, is1786, "related", "Clause 1.2", "Related standard for steel products used in composite structures.")
        ]

        for src, tgt, r_type, clause, desc in relationships:
            existing = db.query(StandardReference).filter(
                StandardReference.source_standard_id == src.id,
                StandardReference.target_standard_id == tgt.id,
                StandardReference.relationship_type == r_type
            ).first()
            if not existing:
                db.add(StandardReference(
                    source_standard_id=src.id,
                    target_standard_id=tgt.id,
                    relationship_type=r_type,
                    clause_reference=clause,
                    description=desc
                ))

        db.commit()
        print("All 7 relationship types successfully seeded!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding relationships: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_extended_relationships()
