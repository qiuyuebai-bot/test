"""Extract searchable text from uploaded knowledge documents."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree


class KnowledgeDocumentParser:
    """Small, deterministic parser for the formats accepted by the upload API."""

    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".json",
        ".csv",
        ".html",
        ".htm",
        ".xml",
        ".rst",
        ".log",
    }

    @classmethod
    def extract(cls, file_name: str, raw_bytes: bytes, fallback_text: Optional[str] = None) -> str:
        """Return readable text or raise a clear error instead of indexing binary data."""
        if fallback_text is not None:
            text = fallback_text
        else:
            extension = Path(file_name).suffix.lower()
            if extension in cls.TEXT_EXTENSIONS:
                text = cls._decode_text(raw_bytes)
            elif extension == ".docx":
                text = cls._extract_docx(raw_bytes)
            elif extension == ".pdf":
                text = cls._extract_pdf(raw_bytes)
            elif extension == ".doc":
                raise ValueError("暂不支持 .doc 二进制文档，请转换为 .docx 或 PDF 后再上传")
            else:
                raise ValueError(f"暂不支持解析文件类型: {extension or '未知'}")

        text = text.replace("\x00", "").strip()
        if not text:
            raise ValueError("文档内容为空，无法建立知识索引")
        return text

    @staticmethod
    def _decode_text(raw_bytes: bytes) -> str:
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                text = raw_bytes.decode(encoding)
                if text.strip():
                    return text
            except UnicodeDecodeError:
                continue
        raise ValueError("文本文件编码无法识别，请使用 UTF-8 或 GB18030")

    @staticmethod
    def _extract_docx(raw_bytes: bytes) -> str:
        try:
            with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
                xml_bytes = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml_bytes)
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise ValueError("DOCX 文件损坏或格式无效") from exc

        paragraphs = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            value = "".join(
                node.text or ""
                for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
            ).strip()
            if value:
                paragraphs.append(value)
        return "\n".join(paragraphs)

    @staticmethod
    def _extract_pdf(raw_bytes: bytes) -> str:
        reader_cls = None
        try:
            from pypdf import PdfReader  # type: ignore

            reader_cls = PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader  # type: ignore

                reader_cls = PdfReader
            except ImportError as exc:
                raise ValueError("服务器未安装 PDF 解析器，请安装 pypdf 后重试") from exc

        try:
            reader = reader_cls(BytesIO(raw_bytes))
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise ValueError("PDF 文件无法解析") from exc
