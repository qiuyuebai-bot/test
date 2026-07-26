"""Safe ReportLab export for learner reports."""
import io
from datetime import datetime
from html import escape
from typing import Any, Dict

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFExporter:
    """Render bounded, escaped report content using a built-in CJK CID font."""

    FONT_NAME = "STSong-Light"

    @classmethod
    def export_report(cls, report: Dict[str, Any]) -> bytes:
        cls._register_font()
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
        styles = getSampleStyleSheet()
        title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName=cls.FONT_NAME, fontSize=20, textColor=HexColor("#1a365d"), alignment=TA_CENTER, spaceAfter=8 * mm)
        heading = ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName=cls.FONT_NAME, fontSize=14, textColor=HexColor("#1a365d"), spaceBefore=6 * mm, spaceAfter=3 * mm)
        body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName=cls.FONT_NAME, fontSize=9, leading=14)
        story = [Paragraph("学情可视化报告", title), Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", body), Spacer(1, 4 * mm)]
        learner = report.get("learner_info", {})
        story.extend([Paragraph("学习者基本信息", heading), cls._table([
            ["字段", "内容"], ["姓名", learner.get("name", "未命名")], ["学历", learner.get("education", "")], ["专业", learner.get("major", "")],
            ["目标行业", learner.get("target_industry", "")], ["目标岗位", learner.get("target_position", "")],
        ], body)])
        metrics = report.get("core_metrics", {})
        story.extend([Paragraph("核心指标", heading), cls._table([
            ["指标", "数值"], ["资源匹配准确率", cls._percent(metrics.get("resource_match_accuracy", 0))],
            ["知识点覆盖率", cls._percent(metrics.get("knowledge_coverage_rate", 0))],
            ["答题正确率", cls._percent(metrics.get("answer_accuracy", 0))],
        ], body)])
        story.extend([Paragraph("能力雷达图数据摘要", heading), cls._table([
            ["能力维度", "得分"], *[
                [item.get("dimension", ""), f"{float(item.get('score', 0)):.1f}"]
                for item in report.get("ability_radar", {}).get("data", [])
            ]
        ] if report.get("ability_radar", {}).get("data") else [["能力维度", "得分"], ["暂无能力数据", "-"]], body)])
        story.extend([Paragraph("知识盲区热力图摘要", heading), cls._table([
            ["能力维度", "严重程度", "得分"], *[
                [item.get("dimension", ""), str(item.get("severity_label", "")), f"{float(item.get('score', 0)):.1f}"]
                for item in report.get("blind_area_heatmap", {}).get("data", [])
            ]
        ] if report.get("blind_area_heatmap", {}).get("data") else [["能力维度", "严重程度", "得分"], ["暂无盲区数据", "-", "-"]], body)])
        path = report.get("learning_path_topology", {})
        story.extend([Paragraph("个性化学习路径", heading), Paragraph(f"当前进度：{cls._percent(path.get('progress', 0))}；预计总时长：{cls._safe(path.get('estimated_total_time', '-'))}", body), cls._table([
            ["阶段", "状态", "预计时间"], *[
                [node.get("name", ""), node.get("status", ""), node.get("estimated_time", "")]
                for node in path.get("nodes", [])
            ]
        ] if path.get("nodes") else [["阶段", "状态", "预计时间"], ["暂无路径", "-", "-"]], body)])
        document.build(story)
        value = buffer.getvalue()
        buffer.close()
        return value

    @classmethod
    def _register_font(cls) -> None:
        if cls.FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(cls.FONT_NAME))

    @classmethod
    def _table(cls, rows: list, style: ParagraphStyle) -> Table:
        escaped_rows = [[Paragraph(cls._safe(cell), style) for cell in row] for row in rows]
        table = Table(escaped_rows, hAlign="LEFT")
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, HexColor("#d9e2ec")), ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f1f5f9")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 5)]))
        return table

    @staticmethod
    def _safe(value: Any) -> str:
        return escape(str(value or "")[:1000]).replace("\n", "<br/>")

    @staticmethod
    def _percent(value: Any) -> str:
        numeric = float(value or 0)
        if 0 <= numeric <= 1:
            numeric *= 100
        return f"{max(0, min(100, numeric)):.1f}%"
