"""Safe ReportLab export for learner reports with real chart renderings."""
import io
import math
from datetime import datetime
from html import escape
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor, toColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.graphics.shapes import Drawing, Polygon, String, Rect, Line, Group
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable


class _RadarChart(Flowable):
    """ReportLab radar (spider) chart for ability dimensions."""

    def __init__(self, points: List[Dict[str, Any]], size: float = 220):
        Flowable.__init__(self)
        self.points = points
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        canvas = self.canv
        center_x = self.width / 2.0
        center_y = self.height / 2.0
        radius = min(self.width, self.height) * 0.38
        labels = [item.get("dimension", f"维度{i}") for i, item in enumerate(self.points)]
        scores = [max(0, min(100, float(item.get("score", 0)))) for item in self.points]
        num_axes = len(self.points)
        if num_axes < 3:
            return

        # Grid rings
        for ring in (0.25, 0.5, 0.75, 1.0):
            ring_points = []
            for index in range(num_axes):
                angle = math.radians(90 - index * 360.0 / num_axes)
                ring_points.extend([
                    center_x + radius * ring * math.cos(angle),
                    center_y + radius * ring * math.sin(angle),
                ])
            path = canvas.beginPath()
            path.moveTo(ring_points[-2], ring_points[-1])
            for index in range(num_axes):
                path.lineTo(ring_points[index * 2], ring_points[index * 2 + 1])
            path.close()
            canvas.setStrokeColor(HexColor("#e2e8f0"))
            canvas.setLineWidth(0.5)
            canvas.drawPath(path, stroke=1, fill=0)

        # Axis lines
        for index in range(num_axes):
            angle = math.radians(90 - index * 360.0 / num_axes)
            canvas.setStrokeColor(HexColor("#cbd5e1"))
            canvas.setLineWidth(0.3)
            canvas.line(center_x, center_y, center_x + radius * math.cos(angle), center_y + radius * math.sin(angle))

        # Data polygon
        data_points = []
        for index in range(num_axes):
            angle = math.radians(90 - index * 360.0 / num_axes)
            value_radius = radius * scores[index] / 100.0
            data_points.extend([
                center_x + value_radius * math.cos(angle),
                center_y + value_radius * math.sin(angle),
            ])
        path = canvas.beginPath()
        path.moveTo(data_points[-2], data_points[-1])
        for index in range(num_axes):
            path.lineTo(data_points[index * 2], data_points[index * 2 + 1])
        path.close()
        canvas.setFillColor(HexColor("#3b82f6"))
        canvas.setFillAlpha(0.2)
        canvas.setStrokeColor(HexColor("#3b82f6"))
        canvas.setLineWidth(1.5)
        canvas.drawPath(path, stroke=1, fill=1)
        canvas.setFillAlpha(1.0)

        # Data point markers
        for index in range(num_axes):
            canvas.setFillColor(HexColor("#3b82f6"))
            canvas.circle(data_points[index * 2], data_points[index * 2 + 1], 3, stroke=1, fill=1)

        # Labels
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HexColor("#475569"))
        for index, label in enumerate(labels):
            angle = math.radians(90 - index * 360.0 / num_axes)
            label_radius = radius + 18
            label_x = center_x + label_radius * math.cos(angle)
            label_y = center_y + label_radius * math.sin(angle)
            canvas.drawCentredString(label_x, label_y - 4, label[:6])

        # Score labels
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor("#1e40af"))
        for index in range(num_axes):
            canvas.drawString(data_points[index * 2] + 4, data_points[index * 2 + 1] + 2, str(int(scores[index])))


class _HeatmapFlowable(Flowable):
    """ReportLab rectangular heatmap for knowledge blind areas."""

    def __init__(self, items: List[Dict[str, Any]], cell_width: float = 90, cell_height: float = 28):
        Flowable.__init__(self)
        self.items = items
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.width = cell_width * 3
        self.height = cell_height * ((len(items) + 2) // 3) + 30

    def draw(self):
        canvas = self.canv
        severity_colors = {"high": HexColor("#ef4444"), "medium": HexColor("#f59e0b"), "low": HexColor("#22c55e")}
        for index, item in enumerate(self.items):
            col = index % 3
            row = index // 3
            x = col * self.cell_width
            y = self.height - (row + 1) * self.cell_height - 20
            severity = item.get("severity", "medium")
            color = severity_colors.get(severity, HexColor("#94a3b8"))
            intensity = min(1.0, max(0.1, float(item.get("value", 30)) / 100.0))
            canvas.setFillColor(color)
            canvas.setFillAlpha(intensity * 0.7 + 0.1)
            canvas.roundRect(x + 2, y + 2, self.cell_width - 4, self.cell_height - 4, 4, stroke=0, fill=1)
            canvas.setFillAlpha(1.0)
            canvas.setStrokeColor(HexColor("#e2e8f0"))
            canvas.setLineWidth(0.5)
            canvas.roundRect(x + 2, y + 2, self.cell_width - 4, self.cell_height - 4, 4, stroke=1, fill=0)
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(HexColor("#1e293b"))
            canvas.drawString(x + 8, y + self.cell_height - 12, str(item.get("dimension", ""))[:8])
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(HexColor("#64748b"))
            score = float(item.get("score", 0))
            canvas.drawString(x + 8, y + 5, f"{score:.0f}分  {'盲区' if item.get('is_blind') else ''}")
        # Legend
        legend_y = 8
        legend_colors = {"高": HexColor("#ef4444"), "中": HexColor("#f59e0b"), "低": HexColor("#22c55e")}
        canvas.setFont("Helvetica", 7)
        offset_x = (self.width - 180) / 2
        for label_text, color in legend_colors.items():
            canvas.setFillColor(color)
            canvas.setFillAlpha(0.5)
            canvas.roundRect(offset_x, legend_y, 12, 8, 2, stroke=0, fill=1)
            canvas.setFillAlpha(1.0)
            canvas.setFillColor(HexColor("#475569"))
            canvas.drawString(offset_x + 16, legend_y, label_text)
            offset_x += 55


def _line_chart_drawing(points: List[Dict[str, Any]], width: float = 400, height: float = 180) -> Drawing:
    """Simple ReportLab line chart for resource difficulty/match curves."""
    drawing = Drawing(width, height)
    scored_points = [item for item in points if item.get("match_score") is not None]
    if not scored_points:
        return drawing
    difficulties = [float(item.get("difficulty", 0)) for item in scored_points]
    match_scores = [max(0, min(100, float(item["match_score"]))) for item in scored_points]
    x_min, x_max = 1, 5
    y_min, y_max = 0, 100
    padding = 40
    plot_width = width - padding * 2
    plot_height = height - padding * 2

    def to_x(value: float) -> float:
        return padding + plot_width * (value - x_min) / max(x_max - x_min, 1)

    def to_y(value: float) -> float:
        return padding + plot_height * (1 - (value - y_min) / max(y_max - y_min, 1))

    # Grid
    for grid_y in range(0, 101, 25):
        draw_y = to_y(grid_y)
        drawing.add(Line(padding, draw_y, width - padding, draw_y, strokeColor=HexColor("#f1f5f9"), strokeWidth=0.5))

    # Axes
    drawing.add(Line(padding, padding, padding, height - padding, strokeColor=HexColor("#cbd5e1"), strokeWidth=1))
    drawing.add(Line(padding, height - padding, width - padding, height - padding, strokeColor=HexColor("#cbd5e1"), strokeWidth=1))

    # Data line
    for index in range(len(difficulties) - 1):
        drawing.add(Line(
            to_x(difficulties[index]), to_y(match_scores[index]),
            to_x(difficulties[index + 1]), to_y(match_scores[index + 1]),
            strokeColor=HexColor("#3b82f6"), strokeWidth=2,
        ))

    # Data points
    for index, (diff, score) in enumerate(zip(difficulties, match_scores)):
        marker_x = to_x(diff)
        marker_y = to_y(score)
        marker = makeMarker("FilledCircle")
        marker.x = marker_x
        marker.y = marker_y
        marker.size = 6
        marker.fillColor = HexColor("#3b82f6")
        marker.strokeColor = HexColor("#ffffff")
        marker.strokeWidth = 1.5
        drawing.add(marker)

    # Labels
    for x_val in range(1, 6):
        draw_x = to_x(x_val)
        drawing.add(String(draw_x, height - padding + 10, str(x_val), fontSize=8, fillColor=HexColor("#64748b"), textAnchor="middle"))
    for y_val in range(0, 101, 25):
        draw_y = to_y(y_val)
        drawing.add(String(padding - 8, draw_y - 5, str(y_val), fontSize=8, fillColor=HexColor("#64748b"), textAnchor="end"))

    drawing.add(String(width / 2, 8, "难度等级", fontSize=8, fillColor=HexColor("#64748b"), textAnchor="middle"))
    return drawing


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

        # Radar chart section
        radar_data = report.get("ability_radar", {}).get("data", [])
        story.append(Paragraph("能力雷达图", heading))
        if radar_data and len(radar_data) >= 3:
            story.append(_RadarChart(radar_data))
        story.append(cls._table([
            ["能力维度", "得分"], *[
                [item.get("dimension", ""), f"{float(item.get('score', 0)):.1f}"]
                for item in radar_data
            ]
        ] if radar_data else [["能力维度", "得分"], ["暂无能力数据", "-"]], body))

        # Heatmap section
        heatmap_data = report.get("blind_area_heatmap", {}).get("data", [])
        story.append(Paragraph("知识盲区热力定位", heading))
        if heatmap_data:
            story.append(_HeatmapFlowable(heatmap_data))
        story.append(cls._table([
            ["能力维度", "严重程度", "得分"], *[
                [item.get("dimension", ""), str(item.get("severity_label", "")), f"{float(item.get('score', 0)):.1f}"]
                for item in heatmap_data
            ]
        ] if heatmap_data else [["能力维度", "严重程度", "得分"], ["暂无盲区数据", "-", "-"]], body))

        # Match curve section
        match_data = report.get("difficulty_match_curve", {}).get("data", [])
        story.append(Paragraph("资源难度匹配曲线", heading))
        if match_data:
            story.append(_line_chart_drawing(match_data))

        # Path section
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
