from io import BytesIO
from zipfile import ZipFile

from app.domains.knowledge.parser import KnowledgeDocumentParser
from app.domains.knowledge.models import KnowledgeSlice
from app.domains.knowledge.schemas import KnowledgeDocCreate
from app.domains.knowledge.service import KnowledgeService


def test_text_parser_supports_utf8_and_rejects_empty():
    assert KnowledgeDocumentParser.extract("notes.txt", "反向传播使用链式法则".encode()) == "反向传播使用链式法则"

    try:
        KnowledgeDocumentParser.extract("empty.txt", b"\x00")
    except ValueError as exc:
        assert "为空" in str(exc)
    else:
        raise AssertionError("empty documents must be rejected")


def test_docx_parser_extracts_paragraph_text():
    document_xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>CNN 是深度学习模型</w:t></w:r></w:p></w:body>
    </w:document>'''.encode("utf-8")
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    assert KnowledgeDocumentParser.extract("guide.docx", buffer.getvalue()) == "CNN 是深度学习模型"


def test_process_doc_marks_error_when_vector_store_is_unavailable(db_session, monkeypatch):
    doc, _ = KnowledgeService.create_doc(
        db_session,
        KnowledgeDocCreate(
            title="向量失败测试",
            industry="人工智能训练",
            file_name="vector-failure.txt",
            file_type="txt",
            file_size=10,
        ),
    )
    assert doc is not None
    monkeypatch.setattr("app.domains.knowledge.service._CHROMA_AVAILABLE", True)
    monkeypatch.setattr("app.domains.knowledge.service._get_chroma_collection", lambda: None)

    assert KnowledgeService.process_doc(db_session, doc.id, "这是一段有效的知识内容") is False
    db_session.refresh(doc)
    assert doc.status == "error"
    assert doc.indexed_slice_count == 0
    assert db_session.query(KnowledgeSlice).filter_by(doc_id=doc.id).count() == 0
