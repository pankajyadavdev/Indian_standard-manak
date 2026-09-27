from datetime import datetime, timezone
import os
import bcrypt
from email_validator import validate_email
from app.db.session import SessionLocal
from app.models.user import User, Role, Permission, Department
from app.models.standard import Standard, StandardVersion, Amendment, StandardReference
from app.models.certification import Certification
from app.models.audit import AuditLog

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def seed_database(include_demo_users: bool = False, demo_password: str | None = None):
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Role).first():
            print("Database already contains roles. Skipping initial seed.")
            return

        print("Seeding database with roles, permissions, departments, standards, and users...")

        # 1. Roles
        roles_data = [
            ("admin", "Platform Super Administrator with full system control"),
            ("procurement_officer", "Tender and procurement management officer"),
            ("technical_reviewer", "Engineering and BIS standards technical reviewer"),
            ("auditor", "Compliance and audit inspection officer"),
            ("viewer", "Read-only access to published tenders and standards")
        ]
        roles = {}
        for r_name, r_desc in roles_data:
            role = Role(name=r_name, description=r_desc)
            db.add(role)
            roles[r_name] = role
        db.flush()

        # 2. Permissions
        permissions_data = [
            ("project:read", "Read project details"),
            ("project:write", "Create and update projects"),
            ("project:delete", "Soft-delete projects"),
            ("tender:read", "Read tender specifications"),
            ("tender:write", "Create and update tenders"),
            ("document:upload", "Upload tender documents"),
            ("document:read", "Read document details and text"),
            ("document:delete", "Soft-delete documents"),
            ("standards:read", "Read standards and versions"),
            ("standards:write", "Manage standards database"),
            ("analysis:run", "Run AI compliance verification pipeline"),
            ("review:submit", "Submit human review comments and decisions"),
            ("review:approve", "Approve or reject procurement recommendations"),
            ("audit:read", "Inspect immutable audit trails"),
            ("admin:all", "Super administrative privileges")
        ]
        permissions = {}
        for p_name, p_desc in permissions_data:
            perm = Permission(name=p_name, description=p_desc)
            db.add(perm)
            permissions[p_name] = perm
        db.flush()

        # Assign permissions
        roles["admin"].permissions = list(permissions.values())
        roles["procurement_officer"].permissions = [
            permissions["project:read"], permissions["project:write"],
            permissions["tender:read"], permissions["tender:write"],
            permissions["document:upload"], permissions["document:read"],
            permissions["standards:read"], permissions["analysis:run"],
            permissions["review:submit"]
        ]
        roles["technical_reviewer"].permissions = [
            permissions["project:read"], permissions["tender:read"],
            permissions["document:read"], permissions["standards:read"],
            permissions["standards:write"], permissions["analysis:run"],
            permissions["review:submit"], permissions["review:approve"]
        ]
        roles["auditor"].permissions = [
            permissions["project:read"], permissions["tender:read"],
            permissions["document:read"], permissions["standards:read"],
            permissions["audit:read"]
        ]
        roles["viewer"].permissions = [
            permissions["project:read"], permissions["tender:read"],
            permissions["standards:read"]
        ]
        db.flush()

        # 3. Departments
        depts_data = [
            ("CPWD", "Central Public Works Department", "Civil infrastructure, buildings, and roads"),
            ("RAILWAYS", "Ministry of Railways (RDSO)", "Railway track, rolling stock, signaling, and electrification"),
            ("DEFENCE", "Directorate General of Quality Assurance (DGQA)", "Defence procurement, armaments, and military engineering"),
            ("POWER", "Central Electricity Authority (CEA)", "Power transmission, substations, and electrical grid systems"),
            ("TELECOM", "Telecommunication Engineering Centre (TEC)", "Telecom infrastructure, optical fibre, and communication towers")
        ]
        depts = {}
        for d_code, d_name, d_desc in depts_data:
            dept = Department(code=d_code, name=d_name, description=d_desc)
            db.add(dept)
            depts[d_code] = dept
        db.flush()

        # Test fixtures can seed demo identities with a per-run password; app defaults create only a bootstrap administrator.
        users_data = []
        if include_demo_users:
            password_bytes = (demo_password or "").encode("utf-8")
            if len(password_bytes) < 16 or len(password_bytes) > 72:
                raise ValueError("A generated demo password of 16-72 UTF-8 bytes is required")
            users_data = [
                ("admin@is-platform.gov.in", demo_password, "Super Administrator", roles["admin"], None),
                ("officer@cpwd.gov.in", demo_password, "Rajesh Kumar (Executive Engineer)", roles["procurement_officer"], depts["CPWD"]),
                ("reviewer@bis.gov.in", demo_password, "Dr. Anita Sharma (Principal Scientist)", roles["technical_reviewer"], depts["CPWD"]),
                ("auditor@cag.gov.in", demo_password, "Vikramaditya Rao (Senior Audit Officer)", roles["auditor"], None),
            ]
        else:
            email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
            password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
            full_name = os.getenv("BOOTSTRAP_ADMIN_NAME", "Platform Administrator").strip()
            try:
                email = validate_email(email, check_deliverability=False).normalized
            except Exception as exc:
                raise ValueError("A valid BOOTSTRAP_ADMIN_EMAIL is required when demo users are disabled") from exc
            password_bytes = password.encode("utf-8")
            if len(password_bytes) < 16 or len(password_bytes) > 72:
                raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must contain 16-72 UTF-8 bytes")
            if len(full_name) < 2 or len(full_name) > 255 or any(ord(char) < 32 for char in full_name):
                raise ValueError("BOOTSTRAP_ADMIN_NAME must contain 2-255 printable characters")
            users_data.append((email, password, full_name, roles["admin"], None))
        for email, pwd, name, role, dept in users_data:
            user = User(
                email=email,
                hashed_password=hash_password(pwd),
                full_name=name,
                role_id=role.id,
                department_id=dept.id if dept else None,
                is_active=True
            )
            db.add(user)
        db.flush()

        # 5. BIS Indian Standards Knowledge Base
        # IS 456
        is456 = Standard(
            standard_code="IS 456",
            title="Plain and Reinforced Concrete - Code of Practice",
            category="Civil",
            status="active",
            scope="Deals with general structural use of plain and reinforced concrete in buildings and civil structures.",
            bis_url="https://standardsbis.bsbedge.com/IS456"
        )
        db.add(is456)
        db.flush()

        v1978 = StandardVersion(
            standard_id=is456.id,
            year=1978,
            version_label="IS 456:1978 (Third Revision)",
            is_current=False,
            changelog="Superseded by IS 456:2000 in July 2000."
        )
        v2000 = StandardVersion(
            standard_id=is456.id,
            year=2000,
            version_label="IS 456:2000 (Fourth Revision)",
            is_current=True,
            effective_date=datetime(2000, 7, 1, tzinfo=timezone.utc),
            changelog="Major revision incorporating limit state design methods and durability requirements."
        )
        db.add_all([v1978, v2000])
        db.flush()
        v1978.superseded_by_version_id = v2000.id

        amendments_is456 = [
            (1, "Amendment No. 1", datetime(2001, 12, 1, tzinfo=timezone.utc), "Clause 5.3 & Table 2 modifications"),
            (2, "Amendment No. 2", datetime(2002, 9, 1, tzinfo=timezone.utc), "Clause 6.2.3.1 environmental exposure adjustments"),
            (3, "Amendment No. 3", datetime(2007, 8, 1, tzinfo=timezone.utc), "Fly ash and slag blending limits updated"),
            (4, "Amendment No. 4", datetime(2013, 5, 1, tzinfo=timezone.utc), "Revising Table 5 minimum cement content"),
            (5, "Amendment No. 5", datetime(2019, 7, 1, tzinfo=timezone.utc), "Self-compacting concrete & high-strength grades M65-M100")
        ]
        for num, code, dt, summary in amendments_is456:
            db.add(Amendment(
                standard_version_id=v2000.id,
                amendment_number=num,
                amendment_code=code,
                issue_date=dt,
                summary=summary
            ))

        # IS 1786
        is1786 = Standard(
            standard_code="IS 1786",
            title="High Strength Deformed Steel Bars and Wires for Concrete Reinforcement - Specification",
            category="Metallurgy & Civil",
            status="active",
            scope="Covers the requirements of deformed steel bars and wires for use as reinforcement in concrete (Fe 415, Fe 500, Fe 550, Fe 600, and Fe 500D grades).",
            bis_url="https://standardsbis.bsbedge.com/IS1786"
        )
        db.add(is1786)
        db.flush()

        v1786_2008 = StandardVersion(
            standard_id=is1786.id,
            year=2008,
            version_label="IS 1786:2008 (Fourth Revision)",
            is_current=True,
            effective_date=datetime(2008, 4, 1, tzinfo=timezone.utc),
            changelog="Introduction of Fe 550D and Fe 600 grades."
        )
        db.add(v1786_2008)
        db.flush()

        db.add_all([
            Amendment(standard_version_id=v1786_2008.id, amendment_number=1, amendment_code="Amendment No. 1", issue_date=datetime(2012, 11, 1, tzinfo=timezone.utc), summary="Phosphorus and sulphur limit revisions"),
            Amendment(standard_version_id=v1786_2008.id, amendment_number=2, amendment_code="Amendment No. 2", issue_date=datetime(2015, 3, 1, tzinfo=timezone.utc), summary="Ductility and elongation criteria for seismic resistance (Fe 500D)"),
            Amendment(standard_version_id=v1786_2008.id, amendment_number=3, amendment_code="Amendment No. 3", issue_date=datetime(2017, 8, 1, tzinfo=timezone.utc), summary="Micro-alloying composition requirements")
        ])

        # Mandatory QCO Certification for IS 1786
        cert_is1786 = Certification(
            standard_id=is1786.id,
            certification_type="ISI Mark - Scheme I",
            is_mandatory=True,
            qco_order_number="S.O. 1671(E) Steel and Steel Products (Quality Control) Order",
            applicable_ministry="Ministry of Steel",
            compliance_category="Mandatory",
            details="No person shall manufacture, import, distribute, sell or store any reinforcement steel bars without BIS Standard Mark (ISI)."
        )
        db.add(cert_is1786)

        # Standard Reference: IS 456 normatively references IS 1786
        ref_456_1786 = StandardReference(
            source_standard_id=is456.id,
            target_standard_id=is1786.id,
            relationship_type="normative",
            clause_reference="Clause 5.6.1",
            description="Reinforcement shall comply with IS 1786 for high strength deformed steel bars."
        )
        db.add(ref_456_1786)

        # IS 2062
        is2062 = Standard(
            standard_code="IS 2062",
            title="Hot Rolled Medium and High Tensile Structural Steel - Specification",
            category="Metallurgy & Civil",
            status="active",
            scope="Covers the requirements of steel plates, sections, flats, and bars for use in structural work.",
            bis_url="https://standardsbis.bsbedge.com/IS2062"
        )
        db.add(is2062)
        db.flush()

        v2062 = StandardVersion(
            standard_id=is2062.id,
            year=2011,
            version_label="IS 2062:2011 (Seventh Revision)",
            is_current=True,
            effective_date=datetime(2011, 10, 1, tzinfo=timezone.utc),
            changelog="Consolidated grades E250 through E650."
        )
        db.add(v2062)
        db.add(Certification(
            standard_id=is2062.id,
            certification_type="ISI Mark - Scheme I",
            is_mandatory=True,
            qco_order_number="Steel and Steel Products QCO 2020",
            applicable_ministry="Ministry of Steel",
            compliance_category="Mandatory",
            details="Mandatory ISI certification for all structural steel supply in government tenders."
        ))

        # IS 694
        is694 = Standard(
            standard_code="IS 694",
            title="Polyvinyl Chloride Insulated Unsheathed-and Sheathed Cables/Cords for Working Voltages up to and Including 450/750 V",
            category="Electrical",
            status="active",
            scope="Specifies requirements for PVC insulated cables for electric power and lighting in domestic and industrial installations.",
            bis_url="https://standardsbis.bsbedge.com/IS694"
        )
        db.add(is694)
        db.flush()

        v694 = StandardVersion(
            standard_id=is694.id,
            year=2010,
            version_label="IS 694:2010 (Fourth Revision)",
            is_current=True,
            effective_date=datetime(2010, 6, 1, tzinfo=timezone.utc)
        )
        db.add(v694)
        db.add(Certification(
            standard_id=is694.id,
            certification_type="ISI Mark - Scheme I",
            is_mandatory=True,
            qco_order_number="Electrical Wires and Cables (Quality Control) Order",
            applicable_ministry="Department for Promotion of Industry and Internal Trade (DPIIT)",
            compliance_category="Mandatory",
            details="Mandatory ISI Mark certification required for all building wire installations."
        ))

        # IS 732
        is732 = Standard(
            standard_code="IS 732",
            title="Code of Practice for Electrical Wiring Installations",
            category="Electrical",
            status="active",
            scope="Covers design, selection, erection, inspection and testing of electrical wiring installations.",
            bis_url="https://standardsbis.bsbedge.com/IS732"
        )
        db.add(is732)
        db.flush()

        v732 = StandardVersion(
            standard_id=is732.id,
            year=2019,
            version_label="IS 732:2019 (Fourth Revision)",
            is_current=True,
            effective_date=datetime(2019, 1, 1, tzinfo=timezone.utc)
        )
        db.add(v732)

        # Normative reference from IS 732 to IS 694
        db.add(StandardReference(
            source_standard_id=is732.id,
            target_standard_id=is694.id,
            relationship_type="normative",
            clause_reference="Clause 6.1.2",
            description="Conductors and wiring cables must satisfy IS 694 specification."
        ))

        # IS 3043 (Earthing)
        is3043 = Standard(
            standard_code="IS 3043",
            title="Code of Practice for Earthing",
            category="Electrical",
            status="active",
            scope="Guidance on installation and maintenance of earthing systems for electrical safety.",
            bis_url="https://standardsbis.bsbedge.com/IS3043"
        )
        db.add(is3043)
        db.flush()
        db.add(StandardVersion(
            standard_id=is3043.id,
            year=2018,
            version_label="IS 3043:2018 (First Revision)",
            is_current=True,
            effective_date=datetime(2018, 1, 1, tzinfo=timezone.utc)
        ))

        # Safety Reference from IS 732 to IS 3043
        db.add(StandardReference(
            source_standard_id=is732.id,
            target_standard_id=is3043.id,
            relationship_type="safety",
            clause_reference="Clause 8.4",
            description="Protective earthing and bonding must comply with IS 3043."
        ))

        # Audit initial seed
        db.add(AuditLog(
            action="system.database_seeded",
            entity_type="system",
            details='{"event": "Initial seed complete with roles, catalogue, versions, amendments, and QCO rules"}'
        ))

        db.commit()
        print("Database successfully seeded with comprehensive BIS dataset!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
