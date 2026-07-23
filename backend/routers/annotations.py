"""
Document Annotations API routes.
Allows users to add notes and highlights to specific documents/pages.
"""

import uuid
from fastapi import APIRouter, HTTPException

from database import execute_query, fetch_one, fetch_all
from schemas import AnnotationCreate, AnnotationOut

router = APIRouter(prefix="/annotations", tags=["Annotations"])


@router.post("", response_model=AnnotationOut, status_code=201)
async def create_annotation(annotation: AnnotationCreate):
    """Create a new annotation on a document."""
    # Verify document exists
    doc = fetch_one(
        "SELECT id FROM documents WHERE id = %s",
        (str(annotation.document_id),),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ann_id = str(uuid.uuid4())
    execute_query(
        """INSERT INTO document_annotations
           (id, document_id, page_number, highlighted_text, note)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            ann_id,
            str(annotation.document_id),
            annotation.page_number,
            annotation.highlighted_text,
            annotation.note,
        ),
    )

    return fetch_one("SELECT * FROM document_annotations WHERE id = %s", (ann_id,))


@router.get("/document/{document_id}", response_model=list[AnnotationOut])
async def list_annotations(document_id: str):
    """List all annotations for a specific document."""
    annotations = fetch_all(
        """SELECT * FROM document_annotations
           WHERE document_id = %s
           ORDER BY created_at DESC""",
        (document_id,),
    )
    return annotations


@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str):
    """Delete a specific annotation."""
    ann = fetch_one(
        "SELECT id FROM document_annotations WHERE id = %s",
        (annotation_id,),
    )
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")

    execute_query(
        "DELETE FROM document_annotations WHERE id = %s",
        (annotation_id,),
    )
    return {"message": "Annotation deleted", "annotation_id": annotation_id}
