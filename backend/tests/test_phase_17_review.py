import os
import uuid

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.recommendation import Evidence, Recommendation
from app.models.review import Review
from app.models.standard import Standard
from app.models.user import User


def login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_recommendation(owner_email="officer@cpwd.gov.in"):
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == owner_email).one()
        standard = db.query(Standard).filter(Standard.standard_code == "IS 456").one()
        version = next((item for item in standard.versions if item.is_current), None)
        department_id = owner.department_id
        project = Project(
            code=f"RV-{uuid.uuid4().hex[:12]}",
            title="Review workflow fixture",
            department_id=department_id,
            created_by_id=owner.id,
        )
        db.add(project)
        db.flush()
        recommendation = Recommendation(
            project_id=project.id,
            standard_id=standard.id,
            version_id=version.id if version else None,
            match_score=0.88,
            confidence_level="High",
            why_justification="The indexed standard scope matches the cited tender requirement.",
            relationship_summary="Direct standards catalogue match.",
            limitations="Verify the current BIS edition before procurement.",
            certification_status="Manual verification required",
            status="pending_review",
        )
        db.add(recommendation)
        db.flush()
        db.add(Evidence(
            recommendation_id=recommendation.id,
            standard_id=standard.id,
            source_text_snippet="IS 456 scope: general structural use of plain and reinforced concrete.",
            confidence_score=0.88,
            evidence_type="standard_scope",
        ))
        db.commit()
        return project.id, recommendation.id
    finally:
        db.close()


def remove_recommendation_fixture(project_id):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
            db.commit()
    finally:
        db.close()


def test_review_queue_returns_evidence_and_is_permission_checked(client):
    project_id, recommendation_id = create_recommendation()
    try:
        officer_headers = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        queue = client.get("/api/v1/reviews/recommendations", headers=officer_headers)
        assert queue.status_code == 200
        row = next(item for item in queue.json()["recommendations"] if item["id"] == recommendation_id)
        assert row["status"] == "pending_review"
        assert row["evidence"][0]["standard_code"] == "IS 456"

        auditor_headers = login(client, "auditor@cag.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        forbidden = client.get("/api/v1/reviews/recommendations", headers=auditor_headers)
        assert forbidden.status_code == 403
    finally:
        remove_recommendation_fixture(project_id)


def test_approval_requires_reviewer_permission_and_persists_decision(client):
    project_id, recommendation_id = create_recommendation()
    try:
        officer_headers = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        forbidden = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "accept", "comments": "Looks relevant."},
            headers=officer_headers,
        )
        assert forbidden.status_code == 403

        reviewer_headers = login(client, "reviewer@bis.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        accepted = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "accept", "comments": "Verified against the cited scope."},
            headers=reviewer_headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"
        assert accepted.json()["review_history"][0]["action"] == "accept"

        duplicate_decision = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "reject", "comments": "Second decision."},
            headers=reviewer_headers,
        )
        assert duplicate_decision.status_code == 409

        db = SessionLocal()
        try:
            record = db.query(Review).filter(Review.recommendation_id == recommendation_id).one()
            assert record.action == "accept"
            assert db.query(AuditLog).filter(
                AuditLog.action == "review.decision",
                AuditLog.entity_id == recommendation_id,
            ).count() == 1
        finally:
            db.close()
    finally:
        remove_recommendation_fixture(project_id)


def test_recommendation_without_evidence_cannot_be_accepted(client):
    project_id, recommendation_id = create_recommendation()
    db = SessionLocal()
    try:
        db.query(Evidence).filter(Evidence.recommendation_id == recommendation_id).delete()
        db.commit()
    finally:
        db.close()

    try:
        reviewer_headers = login(client, "reviewer@bis.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        response = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "accept"},
            headers=reviewer_headers,
        )
        assert response.status_code == 409
    finally:
        remove_recommendation_fixture(project_id)


def test_request_review_and_comments_require_text(client):
    project_id, recommendation_id = create_recommendation()
    try:
        headers = login(client, "officer@cpwd.gov.in", os.environ["TEST_DEMO_PASSWORD"])
        missing_comment = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "request_review"},
            headers=headers,
        )
        assert missing_comment.status_code == 422

        requested = client.post(
            f"/api/v1/reviews/recommendations/{recommendation_id}/actions",
            json={"action": "request_review", "comments": "Please verify the edition and scope."},
            headers=headers,
        )
        assert requested.status_code == 200
        assert requested.json()["status"] == "review_requested"
        assert requested.json()["review_history"][0]["comments"] == "Please verify the edition and scope."
    finally:
        remove_recommendation_fixture(project_id)
