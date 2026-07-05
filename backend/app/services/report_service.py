"""
学情可视化报告与学习路径规划服务
输出结构化图表数据，字段对齐前端Recharts组件需求
"""
import io
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy import func

from app.constants import BLIND_AREA_CRITICAL_THRESHOLD, BLIND_AREA_WARNING_THRESHOLD, DEFAULT_DIFFICULTY
from app.database import get_db_context
from app.models import (
    LearnerProfile,
    LearningResource,
    AnswerRecord,
    TestMetrics,
)
from app.services.common import (
    BaseService,
    LearnerServiceHelper,
    MetricsServiceHelper,
)


class ReportService(BaseService):
    """
    学情可视化报告服务
    """
    
    @classmethod
    def generate_learner_report(cls, learner_id: int) -> Dict[str, Any]:
        """生成完整学情报告"""
        logger.info(f"[报告服务] 生成学情报告: learner_id={learner_id}")
        
        try:
            learner = cls.get_learner(learner_id)
            if not learner:
                return {"success": False, "error": "学习者不存在"}

            # 并行获取各维度数据（优化查询）
            ability_scores = LearnerServiceHelper.get_learner_ability_scores(learner)
            blind_areas = LearnerServiceHelper.get_learner_blind_areas(learner)
            avg_ability = LearnerServiceHelper.get_learner_average_ability(learner)
            
            heatmap_data = cls._generate_blind_area_heatmap(ability_scores, blind_areas)
            match_curve_data = cls._generate_match_curve(learner_id, avg_ability)
            path_topology_data = cls._generate_path_topology(learner, blind_areas)
            ability_radar_data = cls._generate_ability_radar(ability_scores)
            metrics_data = cls._calculate_core_metrics(learner_id, blind_areas)
            
            # 统计信息（合并查询）
            stats = cls._get_statistics(learner_id)
            stats["knowledge_blind_count"] = len(heatmap_data["data"])
            
            report = {
                "success": True,
                "learner_id": learner_id,
                "learner_info": cls._format_learner_info(learner),
                "blind_area_heatmap": heatmap_data,
                "difficulty_match_curve": match_curve_data,
                "learning_path_topology": path_topology_data,
                "ability_radar": ability_radar_data,
                "core_metrics": metrics_data,
                "statistics": stats,
            }
            
            cls.log_request("ReportService", "generate_learner_report", {
                "learner_id": learner_id,
            })
            
            return report
            
        except Exception as e:
            logger.error(f"[报告服务] 生成报告失败: {e}")
            cls.log_error("生成报告失败", e)
            return {"success": False, "error": str(e)}
    
    @classmethod
    def _format_learner_info(cls, learner: LearnerProfile) -> Dict[str, Any]:
        """格式化学习者信息"""
        return {
            "id": learner.id,
            "name": learner.real_name or "未命名",
            "education": learner.education_level or "",
            "major": learner.major or "",
            "learning_style": learner.learning_style or "visual",
            "target_industry": learner.target_industry or "",
            "target_position": learner.target_position or "",
        }
    
    @classmethod
    def _generate_blind_area_heatmap(
        cls,
        ability_scores: Dict[str, float],
        blind_areas: List[str],
    ) -> Dict[str, Any]:
        """生成知识盲区热力图数据"""
        heatmap_data = []
        
        for field_key, field_name in cls.ABILITY_DIMENSIONS:
            score = ability_scores.get(field_key, 0)
            
            # 判断严重程度
            if score < BLIND_AREA_CRITICAL_THRESHOLD:
                severity, severity_label, value = "high", "高", 90
            elif score < BLIND_AREA_WARNING_THRESHOLD:
                severity, severity_label, value = "medium", "中", 60
            else:
                severity, severity_label, value = "low", "低", 30
            
            is_blind = any(field_name in area for area in blind_areas)
            
            heatmap_data.append({
                "dimension": field_name,
                "dimension_key": field_key,
                "severity": severity,
                "severity_label": severity_label,
                "value": value if is_blind else value * 0.5,
                "score": score,
                "is_blind": is_blind,
                "description": cls._get_blind_description(field_name, score),
            })
        
        return {
            "labels": [name for _, name in cls.ABILITY_DIMENSIONS],
            "severity_levels": ["high", "medium", "low"],
            "severity_labels": ["高", "中", "低"],
            "data": heatmap_data,
        }
    
    @classmethod
    def _generate_match_curve(
        cls,
        learner_id: int,
        avg_ability: float,
    ) -> Dict[str, Any]:
        """生成资源难度匹配曲线数据"""
        with get_db_context() as db:
            resources = (
                db.query(LearningResource)
                .filter(LearningResource.learner_id == learner_id)
                .order_by(LearningResource.created_at)
                .limit(10)
                .all()
            )
        
        labels = []
        difficulty_data = []
        match_data = []
        data_points = []
        
        for i, r in enumerate(resources):
            labels.append(f"资源{i+1}")
            difficulty_data.append(r.difficulty_level or DEFAULT_DIFFICULTY)
            match_data.append(r.match_score or 70)
            
            data_points.append({
                "name": f"资源{i+1}",
                "difficulty": r.difficulty_level or DEFAULT_DIFFICULTY,
                "match_score": r.match_score or 70,
                "learner_ability": avg_ability / 20,
                "resource_id": r.id,
                "title": r.title,
            })
        
        return {
            "labels": labels,
            "difficulty": difficulty_data,
            "match_score": match_data,
            "learner_ability": [avg_ability / 20] * len(labels),
            "data": data_points,
            "learner_ability_raw": avg_ability,
        }
    
    @classmethod
    def _generate_path_topology(
        cls,
        learner: LearnerProfile,
        blind_areas: List[str],
    ) -> Dict[str, Any]:
        """生成学习路径节点拓扑数据"""
        with get_db_context() as db:
            # 仅取最近 100 条资源避免全表加载（路径拓扑仅展示 ~8 个节点）
            resources = (
                db.query(LearningResource)
                .filter(LearningResource.learner_id == learner.id)
                .order_by(LearningResource.difficulty_level)
                .limit(100)
                .all()
            )
        
        # 构建资源映射
        resources_by_diff = {}
        for r in resources:
            diff = r.difficulty_level or DEFAULT_DIFFICULTY
            if diff not in resources_by_diff:
                resources_by_diff[diff] = []
            resources_by_diff[diff].append({
                "resource_id": r.id,
                "title": r.title,
                "type": r.resource_type,
                "match_score": r.match_score,
            })
        
        nodes = []
        edges = []
        
        # 阶段1: 基础
        for i, (name, time_val) in enumerate([("基础概念", "2小时"), ("入门实践", "4小时")]):
            node_id = f"step-{i+1}"
            nodes.append({
                "id": node_id,
                "name": name,
                "difficulty": i + 1,
                "status": "completed" if i < 2 else "current",
                "estimated_time": time_val,
                "resources": resources_by_diff.get(i + 1, []),
                "description": ["建立知识框架", "动手实践基础案例"][i],
            })
        
        # 阶段2: 进阶
        step_idx = 3
        for blind in blind_areas[:3]:
            nodes.append({
                "id": f"step-{step_idx}",
                "name": blind,
                "difficulty": 3,
                "status": "current" if step_idx == 3 else "locked",
                "estimated_time": "6小时",
                "resources": resources_by_diff.get(3, []),
                "description": f"专项突破：{blind}",
            })
            step_idx += 1
        
        # 阶段3: 高级
        for i, (name, desc, time_val) in enumerate([
            ("进阶应用", "深入理解核心原理", "8小时"),
            ("综合实战", "完成综合项目实战", "12小时"),
        ]):
            nodes.append({
                "id": f"step-{step_idx + i}",
                "name": name,
                "difficulty": i + 4,
                "status": "locked",
                "estimated_time": time_val,
                "resources": resources_by_diff.get(i + 4, []),
                "description": desc,
            })
        
        # 添加边
        for i in range(len(nodes) - 1):
            edges.append({"source": nodes[i]["id"], "target": nodes[i + 1]["id"]})
        
        return {
            "total_steps": len(nodes),
            "current_step": 3,
            "progress": 37.5,
            "estimated_total_time": "32小时",
            "nodes": nodes,
            "edges": edges,
        }
    
    @classmethod
    def _generate_ability_radar(
        cls,
        ability_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """生成能力雷达图数据"""
        data_points = []
        for field_key, field_name in cls.ABILITY_DIMENSIONS:
            score = ability_scores.get(field_key, 0)
            data_points.append({
                "dimension": field_name,
                "score": score,
                "fullMark": 100,
            })
        
        avg_score = sum(ability_scores.values()) / len(ability_scores) if ability_scores else 0
        
        return {
            "dimensions": [name for _, name in cls.ABILITY_DIMENSIONS],
            "data": data_points,
            "average_score": avg_score,
        }
    
    @classmethod
    def _calculate_core_metrics(
        cls,
        learner_id: int,
        blind_areas: List[str],
    ) -> Dict[str, Any]:
        """计算核心评审指标"""
        with get_db_context() as db:
            # 资源匹配准确率：SQL AVG 聚合，避免加载全部资源到内存
            resource_match_accuracy = (
                db.query(func.avg(LearningResource.match_score))
                .filter(LearningResource.learner_id == learner_id)
                .scalar()
            ) or 0

            # 知识点覆盖率：substring 匹配无法纯 SQL，仅取 content 列降低内存占用
            if blind_areas:
                contents = (
                    db.query(LearningResource.content)
                    .filter(LearningResource.learner_id == learner_id)
                    .all()
                )
                covered_blind = sum(
                    1 for (content,) in contents
                    if any(blind in (content or "") for blind in blind_areas)
                )
                knowledge_coverage_rate = covered_blind / len(blind_areas) * 100
            else:
                knowledge_coverage_rate = 100

            # 答题正确率：SQL COUNT 聚合
            total_answers = (
                db.query(AnswerRecord)
                .filter(AnswerRecord.learner_id == learner_id)
                .count()
            )
            correct_answers = (
                db.query(AnswerRecord)
                .filter(
                    AnswerRecord.learner_id == learner_id,
                    AnswerRecord.result == "correct",
                )
                .count()
            )
            answer_accuracy = (
                correct_answers / total_answers * 100 if total_answers > 0 else 0
            )

        return {
            "resource_match_accuracy": round(resource_match_accuracy, 2),
            "knowledge_coverage_rate": round(knowledge_coverage_rate, 2),
            "answer_accuracy": round(answer_accuracy, 2),
        }
    
    @classmethod
    def _get_statistics(cls, learner_id: int) -> Dict[str, Any]:
        """获取统计信息"""
        with get_db_context() as db:
            resource_count = (
                db.query(LearningResource)
                .filter(LearningResource.learner_id == learner_id)
                .count()
            )
            
            answers = (
                db.query(AnswerRecord)
                .filter(AnswerRecord.learner_id == learner_id)
                .all()
            )
            
            avg_score = 0
            if answers:
                total_score = sum(a.score or 0 for a in answers)
                avg_score = round(total_score / len(answers), 2)
            
            return {
                "total_resources": resource_count,
                "total_answers": len(answers),
                "avg_answer_score": avg_score,
            }
    
    @classmethod
    def _get_blind_description(cls, dimension: str, score: float) -> str:
        """获取盲区描述"""
        if score < BLIND_AREA_CRITICAL_THRESHOLD:
            return f"{dimension}能力薄弱，需要重点提升"
        elif score < BLIND_AREA_WARNING_THRESHOLD:
            return f"{dimension}基础一般，建议加强练习"
        return f"{dimension}掌握良好，可适当拓展"
    
    @classmethod
    def export_report_pdf(cls, learner_id: int) -> Optional[bytes]:
        """
        导出学情报告为 PDF
        
        Args:
            learner_id: 学习者ID
            
        Returns:
            PDF 字节流，失败返回 None
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, grey
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
        
        # 生成报告数据
        report = cls.generate_learner_report(learner_id)
        if not report.get("success"):
            return None
        
        buffer = io.BytesIO()
        
        # 文档设置
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=25*mm,
            rightMargin=25*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
            title=f"学情报告 - {report['learner_info']['name']}",
        )
        
        # 样式定义
        styles = getSampleStyleSheet()
        
        # 自定义颜色
        primary_color = HexColor("#1a365d")      # 深空蓝
        secondary_color = HexColor("#4a5568")    # 灰色
        accent_color = HexColor("#2b6cb0")       # 亮蓝
        light_bg = HexColor("#f7fafc")           # 浅灰背景
        border_color = HexColor("#e2e8f0")       # 边框色
        success_color = HexColor("#38a169")      # 绿色
        warning_color = HexColor("#d69e2e")      # 黄色
        danger_color = HexColor("#e53e3e")       # 红色
        
        # 自定义样式
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=primary_color,
            spaceAfter=6*mm,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
        
        subtitle_style = ParagraphStyle(
            "CustomSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=secondary_color,
            alignment=TA_CENTER,
            spaceAfter=12*mm,
        )
        
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=primary_color,
            spaceBefore=10*mm,
            spaceAfter=5*mm,
            fontName="Helvetica-Bold",
        )

        body_style = ParagraphStyle(
            "CustomBody",
            parent=styles["Normal"],
            fontSize=9,
            textColor=secondary_color,
            leading=14,
            spaceAfter=2*mm,
        )
        
        metric_label_style = ParagraphStyle(
            "MetricLabel",
            parent=styles["Normal"],
            fontSize=8,
            textColor=grey,
            alignment=TA_CENTER,
        )
        
        metric_value_style = ParagraphStyle(
            "MetricValue",
            parent=styles["Normal"],
            fontSize=18,
            textColor=primary_color,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
        
        # 构建内容
        story = []
        
        learner_info = report["learner_info"]
        core_metrics = report["core_metrics"]
        statistics = report["statistics"]
        heatmap = report["blind_area_heatmap"]
        match_curve = report["difficulty_match_curve"]
        path_topology = report["learning_path_topology"]
        ability_radar = report["ability_radar"]
        
        # === 封面标题 ===
        story.append(Spacer(1, 15*mm))
        story.append(Paragraph("学情可视化报告", title_style))
        story.append(Paragraph(
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style,
        ))
        
        # 分隔线
        story.append(HRFlowable(width="100%", thickness=0.5, color=border_color))
        story.append(Spacer(1, 5*mm))
        
        # === 学习者信息 ===
        story.append(Paragraph("学习者基本信息", h1_style))
        info_data = [
            [Paragraph("<b>姓名</b>", body_style), Paragraph(learner_info.get("name", ""), body_style)],
            [Paragraph("<b>学历</b>", body_style), Paragraph(learner_info.get("education", ""), body_style)],
            [Paragraph("<b>专业</b>", body_style), Paragraph(learner_info.get("major", ""), body_style)],
            [Paragraph("<b>目标行业</b>", body_style), Paragraph(learner_info.get("target_industry", ""), body_style)],
            [Paragraph("<b>目标岗位</b>", body_style), Paragraph(learner_info.get("target_position", ""), body_style)],
            [Paragraph("<b>学习风格</b>", body_style), Paragraph(learner_info.get("learning_style", ""), body_style)],
        ]
        info_table = Table(info_data, colWidths=[40*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(info_table)
        
        # === 核心指标卡片 ===
        story.append(Paragraph("核心评审指标", h1_style))
        metrics_grid = [
            [
                Paragraph("资源匹配准确率", metric_label_style),
                Paragraph("知识点覆盖率", metric_label_style),
                Paragraph("答题正确率", metric_label_style),
            ],
            [
                Paragraph(f"{core_metrics.get('resource_match_accuracy', 0):.1f}%", metric_value_style),
                Paragraph(f"{core_metrics.get('knowledge_coverage_rate', 0):.1f}%", metric_value_style),
                Paragraph(f"{core_metrics.get('answer_accuracy', 0):.1f}%", metric_value_style),
            ],
        ]
        metrics_table = Table(metrics_grid, colWidths=[53*mm, 53*mm, 53*mm])
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 3*mm))
        
        # 统计信息
        stats_data = [
            [Paragraph("<b>统计项</b>", body_style), Paragraph("<b>数值</b>", body_style)],
            [Paragraph("生成资源总数", body_style), Paragraph(str(statistics.get("total_resources", 0)), body_style)],
            [Paragraph("答题总数", body_style), Paragraph(str(statistics.get("total_answers", 0)), body_style)],
            [Paragraph("平均答题得分", body_style), Paragraph(f"{statistics.get('avg_answer_score', 0):.1f}", body_style)],
            [Paragraph("知识盲区数量", body_style), Paragraph(str(statistics.get("knowledge_blind_count", 0)), body_style)],
        ]
        stats_table = Table(stats_data, colWidths=[80*mm, 80*mm])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(stats_table)
        
        # === 知识盲区分析 ===
        story.append(Paragraph("知识盲区热力图分析", h1_style))
        
        heatmap_header = [
            [Paragraph("<b>能力维度</b>", body_style), Paragraph("<b>得分</b>", body_style),
             Paragraph("<b>严重程度</b>", body_style), Paragraph("<b>是否盲区</b>", body_style)],
        ]
        heatmap_rows = []
        for item in heatmap.get("data", []):
            severity_color = danger_color if item["severity"] == "high" else (
                warning_color if item["severity"] == "medium" else success_color
            )
            heatmap_rows.append([
                Paragraph(item["dimension"], body_style),
                Paragraph(f"{item['score']:.0f}", body_style),
                Paragraph(f'<font color="{severity_color}">{item["severity_label"]}</font>', body_style),
                Paragraph("是" if item["is_blind"] else "否", body_style),
            ])
        
        heatmap_table = Table(heatmap_header + heatmap_rows, colWidths=[50*mm, 30*mm, 40*mm, 40*mm])
        heatmap_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(heatmap_table)
        
        # === 能力雷达图摘要 ===
        story.append(Paragraph("能力维度评估", h1_style))
        radar = ability_radar
        story.append(Paragraph(
            f"综合能力平均分: <b>{radar.get('average_score', 0):.1f}</b> / 100",
            body_style,
        ))
        
        radar_header = [[Paragraph("<b>能力维度</b>", body_style), Paragraph("<b>得分</b>", body_style)]]
        radar_rows = []
        for item in radar.get("data", []):
            radar_rows.append([
                Paragraph(item["dimension"], body_style),
                Paragraph(f"{item['score']:.0f}", body_style),
            ])
        
        radar_table = Table(radar_header + radar_rows, colWidths=[80*mm, 80*mm])
        radar_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(radar_table)
        
        # === 资源难度匹配 ===
        story.append(Paragraph("资源难度匹配曲线", h1_style))
        if match_curve.get("data"):
            curve_header = [
                [Paragraph("<b>资源名称</b>", body_style), Paragraph("<b>难度</b>", body_style),
                 Paragraph("<b>匹配度</b>", body_style)],
            ]
            curve_rows = []
            for item in match_curve.get("data", [])[:6]:
                match_color = success_color if (item.get("match_score", 0) or 0) >= 80 else (
                    warning_color if (item.get("match_score", 0) or 0) >= 60 else danger_color
                )
                curve_rows.append([
                    Paragraph(item.get("title", item.get("name", "")), body_style),
                    Paragraph(str(item.get("difficulty", "-")), body_style),
                    Paragraph(
                        f'<font color="{match_color}">{item.get("match_score", 0) or 0:.0f}%</font>',
                        body_style,
                    ),
                ])
            
            curve_table = Table(curve_header + curve_rows, colWidths=[80*mm, 40*mm, 40*mm])
            curve_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), light_bg),
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(curve_table)
        else:
            story.append(Paragraph("暂无资源匹配数据", body_style))
        
        # === 学习路径规划 ===
        story.append(Paragraph("学习路径规划", h1_style))
        story.append(Paragraph(
            f"当前进度: <b>{path_topology.get('progress', 0):.1f}%</b> | "
            f"总步骤: {path_topology.get('total_steps', 0)} | "
            f"预计总时间: {path_topology.get('estimated_total_time', '未知')}",
            body_style,
        ))
        
        path_header = [
            [Paragraph("<b>阶段</b>", body_style), Paragraph("<b>名称</b>", body_style),
             Paragraph("<b>难度</b>", body_style), Paragraph("<b>状态</b>", body_style),
             Paragraph("<b>预计时间</b>", body_style)],
        ]
        path_rows = []
        for node in path_topology.get("nodes", []):
            status_map = {"completed": "已完成", "current": "进行中", "locked": "待解锁"}
            status_color = {"completed": success_color, "current": accent_color, "locked": grey}
            status = status_map.get(node.get("status", ""), node.get("status", ""))
            sc = status_color.get(node.get("status", ""), grey)
            path_rows.append([
                Paragraph(str(node.get("difficulty", "")), body_style),
                Paragraph(node.get("name", ""), body_style),
                Paragraph("★" * node.get("difficulty", 1), body_style),
                Paragraph(f'<font color="{sc}">{status}</font>', body_style),
                Paragraph(node.get("estimated_time", ""), body_style),
            ])
        
        path_table = Table(path_header + path_rows, colWidths=[20*mm, 50*mm, 30*mm, 30*mm, 30*mm])
        path_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), light_bg),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(path_table)
        
        # === 页脚 ===
        story.append(Spacer(1, 15*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=border_color))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            "本报告由领域知识个性化生成与多智能体协同决策系统自动生成 | "
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=7,
                textColor=grey,
                alignment=TA_CENTER,
            ),
        ))
        
        # 生成 PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"[报告服务] PDF 生成完成: learner_id={learner_id}, size={len(pdf_bytes)} bytes")
        
        return pdf_bytes
    
    @classmethod
    def update_metrics_periodically(cls) -> None:
        """定时更新指标统计"""
        logger.info("[报告服务] 定时更新指标统计")

        try:
            with get_db_context() as db:
                # 仅查询需要的字段，避免全表加载整个模型
                learner_rows = (
                    db.query(LearnerProfile.id, LearnerProfile.knowledge_blind_areas)
                    .all()
                )

                # 单查询：按 learner_id 聚合平均 match_score（避免 N+1）
                per_learner_avg = (
                    db.query(
                        LearningResource.learner_id,
                        func.avg(LearningResource.match_score).label("avg_match"),
                    )
                    .group_by(LearningResource.learner_id)
                    .all()
                )
                valid_avgs = [row.avg_match for row in per_learner_avg if row.avg_match is not None]
                overall_match_accuracy = (
                    sum(valid_avgs) / len(valid_avgs) if valid_avgs else 0
                )

                # 更新指标表
                metrics = MetricsServiceHelper.get_or_create_daily_metrics(db)
                MetricsServiceHelper.init_metrics_fields(metrics)
                metrics.resource_match_accuracy = overall_match_accuracy

                # 单查询：所有资源的 (learner_id, content)，按 learner_id 分组后在内存做 substring 匹配
                total_blind = sum(len(r.knowledge_blind_areas or []) for r in learner_rows)
                all_resources = (
                    db.query(LearningResource.learner_id, LearningResource.content)
                    .all()
                )
                resources_by_learner: Dict[int, List[str]] = {}
                for lid, content in all_resources:
                    resources_by_learner.setdefault(lid, []).append(content or "")

                total_covered = 0
                for lid, blind_areas in learner_rows:
                    if not blind_areas:
                        continue
                    learner_contents = resources_by_learner.get(lid, [])
                    for content in learner_contents:
                        for blind in blind_areas:
                            if blind in content:
                                total_covered += 1
                                break

                metrics.knowledge_coverage_rate = (
                    total_covered / total_blind * 100 if total_blind > 0 else 0
                )

                db.commit()

                logger.info(
                    f"[报告服务] 指标更新完成: 匹配准确率={overall_match_accuracy:.2f}"
                )

        except Exception as e:
            logger.error(f"[报告服务] 指标更新失败: {e}")
            cls.log_error("指标更新失败", e)
    
    @classmethod
    def get_system_metrics(cls) -> Dict[str, Any]:
        """获取系统级指标"""
        with get_db_context() as db:
            # 获取最近7天指标趋势
            metrics = (
                db.query(TestMetrics)
                .filter(TestMetrics.record_period == "daily")
                .order_by(TestMetrics.record_date.desc())
                .limit(7)
                .all()
            )
            
            # 统计数据
            from app.models import LearnerProfile, LearningResource, AnswerRecord
            
            learner_count = db.query(LearnerProfile).count()
            resource_count = db.query(LearningResource).count()
            answer_count = db.query(AnswerRecord).count()
            
            latest = metrics[0] if metrics else None
            
            trends = [
                {
                    "date": m.record_date,
                    "metrics": {
                        "hallucinationRate": m.hallucination_rate or 0,
                        "resourceMatchAccuracy": m.resource_match_accuracy or 0,
                        "knowledgeCoverage": m.knowledge_coverage_rate or 0,
                    },
                }
                for m in reversed(metrics)
            ]
            
            return {
                "hallucination_rate": latest.hallucination_rate if latest else 0,
                "resource_match_accuracy": latest.resource_match_accuracy if latest else 0,
                "knowledge_coverage_rate": latest.knowledge_coverage_rate if latest else 0,
                "total_learners": learner_count,
                "total_resources": resource_count,
                "total_answers": answer_count,
                "active_sessions": 0,
                "avg_completion_time": "-",
                "satisfaction_score": 0,
                "trends": trends,
            }
