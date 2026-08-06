from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import deliverable_dict, document_dict, pile_dict, rule_dict
from app.models import DeliverableVersion, Document, Pile, Rule
from app.schemas import AddRuleRequest, CreatePileRequest
from app.services.runs import add_rule, create_pile, upload_document

router = APIRouter(prefix="/piles", tags=["piles"])


@router.post("")
def create_pile_endpoint(body: CreatePileRequest, db: Session = Depends(get_db)):
    pile = create_pile(db, body.name, body.domain)
    return pile_dict(pile)


@router.get("/{pile_id}")
def get_pile(pile_id: str, db: Session = Depends(get_db)):
    pile = db.get(Pile, pile_id)
    if not pile:
        raise HTTPException(404, "pile not found")
    return pile_dict(pile)


@router.post("/{pile_id}/rules")
def add_rule_endpoint(pile_id: str, body: AddRuleRequest, db: Session = Depends(get_db)):
    if not db.get(Pile, pile_id):
        raise HTTPException(404, "pile not found")
    rule = add_rule(db, pile_id, body.text)
    return rule_dict(rule)


@router.get("/{pile_id}/rules")
def list_rules(pile_id: str, db: Session = Depends(get_db)):
    rules = db.query(Rule).filter(Rule.pile_id == pile_id).all()
    return [rule_dict(r) for r in rules]


@router.post("/{pile_id}/documents")
async def upload_document_endpoint(pile_id: str, file: UploadFile, db: Session = Depends(get_db)):
    if not db.get(Pile, pile_id):
        raise HTTPException(404, "pile not found")
    data = await file.read()
    doc = upload_document(db, pile_id, file.filename, data)
    return document_dict(doc)


@router.get("/{pile_id}/documents")
def list_documents(pile_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.pile_id == pile_id).all()
    return [document_dict(d) for d in docs]


@router.get("/{pile_id}/deliverable")
def get_latest_deliverable(pile_id: str, db: Session = Depends(get_db)):
    deliverable = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.pile_id == pile_id, DeliverableVersion.is_committed.is_(True))
        .order_by(DeliverableVersion.version_number.desc())
        .first()
    )
    if not deliverable:
        raise HTTPException(404, "no committed deliverable yet")
    return deliverable_dict(deliverable)


@router.get("/{pile_id}/deliverable/history")
def get_deliverable_history(pile_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(DeliverableVersion)
        .filter(DeliverableVersion.pile_id == pile_id, DeliverableVersion.is_committed.is_(True))
        .order_by(DeliverableVersion.version_number.asc())
        .all()
    )
    return [deliverable_dict(v) for v in versions]
