import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, Role, Permission, Department
from app.models.project import Project, Tender
from app.models.document import Document
from app.models.standard import Standard, StandardVersion, Amendment, StandardReference
from app.models.certification import Certification
from app.models.recommendation import Recommendation, Evidence
from app.models.review import Review
from app.models.audit import AuditLog

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_roles_and_permissions(db_session: Session):
    admin_role = db_session.query(Role).filter(Role.name == "admin").first()
    assert admin_role is not None
    assert len(admin_role.permissions) > 0
    perm_names = [p.name for p in admin_role.permissions]
    assert "admin:all" in perm_names
    assert "review:approve" in perm_names

def test_users_and_departments(db_session: Session):
    user = db_session.query(User).filter(User.email == "officer@cpwd.gov.in").first()
    assert user is not None
    assert user.role.name == "procurement_officer"
    assert user.department is not None
    assert user.department.code == "CPWD"
    assert user.is_active is True

def test_standards_and_versions(db_session: Session):
    is456 = db_session.query(Standard).filter(Standard.standard_code == "IS 456").first()
    assert is456 is not None
    assert len(is456.versions) == 2
    
    current_ver = [v for v in is456.versions if v.is_current][0]
    assert current_ver.year == 2000
    assert len(current_ver.amendments) == 5

    old_ver = [v for v in is456.versions if not v.is_current][0]
    assert old_ver.year == 1978
    assert old_ver.superseded_by_version_id == current_ver.id

def test_standard_references(db_session: Session):
    is456 = db_session.query(Standard).filter(Standard.standard_code == "IS 456").first()
    refs = is456.outbound_references
    assert len(refs) > 0
    target_codes = [ref.target_standard.standard_code for ref in refs]
    assert "IS 1786" in target_codes

def test_certifications_qco(db_session: Session):
    is1786 = db_session.query(Standard).filter(Standard.standard_code == "IS 1786").first()
    assert is1786 is not None
    assert len(is1786.certifications) > 0
    cert = is1786.certifications[0]
    assert cert.is_mandatory is True
    assert cert.compliance_category == "Mandatory"

def test_soft_delete(db_session: Session):
    # Test soft delete mixin
    test_dept = Department(code="TEST_DEPT", name="Test Department")
    db_session.add(test_dept)
    db_session.commit()
    
    dept_id = test_dept.id
    assert test_dept.is_deleted is False
    assert test_dept.deleted_at is None
    
    test_dept.soft_delete()
    db_session.commit()
    
    reloaded = db_session.query(Department).filter(Department.id == dept_id).first()
    assert reloaded.is_deleted is True
    assert reloaded.deleted_at is not None
    
    # Clean up
    db_session.delete(reloaded)
    db_session.commit()

def test_audit_log_append_only(db_session: Session):
    log = AuditLog(
        action="test.action",
        entity_type="test_entity",
        details='{"test": true}'
    )
    db_session.add(log)
    db_session.commit()
    
    assert log.id is not None
    assert log.timestamp is not None
    
    # Clean up
    db_session.delete(log)
    db_session.commit()
