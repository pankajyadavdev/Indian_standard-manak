from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.document import Document
from app.models.project import Project
from app.models.user import User


def visible_document_query(db: Session, user: User) -> Query:
    """Return active documents whose owning project is visible to this user."""
    query = (
        db.query(Document)
        .join(Project, Document.project_id == Project.id)
        .filter(Document.is_deleted.is_(False), Project.is_deleted.is_(False))
    )
    if not user.role or user.role.name != "admin":
        scope = [Project.created_by_id == user.id]
        if user.department_id:
            scope.append(Project.department_id == user.department_id)
        query = query.filter(or_(*scope))
    return query
