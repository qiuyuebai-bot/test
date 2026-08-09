"""
学情可视化报告与学习路径规划服务
输出结构化图表数据，字段对齐前端Recharts组件需求
"""
from typing import Dict, Any, List, Optional
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
from app.services.path_planner import PathPlanner
from app.utils.llm import LLMUtil
from app.utils.metrics import MetricsUtil
from app.utils.datetime import utcnow_naive


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
            raw_match_score = r.match_score if r.match_score is not None else 70
            match_score = raw_match_score * 100 if 0 <= raw_match_score <= 1 else raw_match_score
            match_data.append(match_score)

            data_points.append({
                "name": f"资源{i+1}",
                "difficulty": r.difficulty_level or DEFAULT_DIFFICULTY,
                "match_score": match_score,
                "learner_ability": avg_ability,
                "resource_id": r.id,
                "title": r.title,
            })
        
        return {
            "labels": labels,
            "difficulty": difficulty_data,
            "match_score": match_data,
            "learner_ability": [avg_ability] * len(labels),
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
        
        if LLMUtil.is_available():
            try:
                return PathPlanner.plan_path(learner, blind_areas, [
                    resource for group in resources_by_diff.values() for resource in group
                ])
            except Exception as exc:
                logger.warning(f"[报告服务] LLM 学习路径规划失败，使用规则兜底: {exc}")

        nodes = []
        edges = []

        # 阶段1: 基础
        for i, (name, time_val) in enumerate([("基础概念", "2小时"), ("入门实践", "4小时")]):
            node_id = f"step-{i+1}"
            nodes.append({
                "id": node_id,
                "name": name,
                "difficulty": i + 1,
                "status": "completed" if i == 0 else "current",
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
        
        current_step = next((index for index, node in enumerate(nodes, 1) if node["status"] == "current"), len(nodes))
        completed_steps = sum(node["status"] == "completed" for node in nodes)
        total_hours = sum(int("".join(char for char in node["estimated_time"] if char.isdigit()) or 0) for node in nodes)
        return {
            "total_steps": len(nodes),
            "current_step": current_step,
            "progress": round(completed_steps / len(nodes) * 100, 1) if nodes else 0,
            "estimated_total_time": f"{total_hours}小时",
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
        from app.services.pdf_exporter import PDFExporter
        report = cls.generate_learner_report(learner_id)
        if not report.get("success"):
            return None
        return PDFExporter.export_report(report)
    
    @classmethod
    def update_metrics_periodically(cls) -> None:
        """定时更新指标统计"""
        logger.info("[报告服务] 定时更新指标统计")

        try:
            with get_db_context() as db:
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

                # 系统覆盖率统一使用知识库切片索引覆盖率。学习者盲区覆盖率
                # 单独记录，避免两个不同算法共用 knowledge_coverage_rate。
                knowledge_index_coverage_rate = MetricsUtil.calculate_knowledge_index_coverage_rate(db)
                learning_blind_spot_coverage_rate = MetricsUtil.calculate_learning_blind_spot_coverage_rate(db)
                metrics.knowledge_coverage_rate = knowledge_index_coverage_rate
                metrics.detailed_metrics = {
                    **(metrics.detailed_metrics or {}),
                    "knowledge_index_coverage_rate": knowledge_index_coverage_rate,
                    "learning_blind_spot_coverage_rate": learning_blind_spot_coverage_rate,
                }

                db.commit()

                logger.info(
                    f"[报告服务] 指标更新完成: 匹配准确率={overall_match_accuracy:.2f}, "
                    f"知识库索引覆盖率={knowledge_index_coverage_rate}"
                )

        except Exception as e:
            logger.error(f"[报告服务] 指标更新失败: {e}")
            cls.log_error("指标更新失败", e)
    
    @classmethod
    def get_system_metrics(cls) -> Dict[str, Any]:
        """获取系统级指标"""
        with get_db_context() as db:
            hallucination_metrics = MetricsUtil.calculate_hallucination_metrics(db)
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
            
            # 当前卡片指标使用实时数据；快照只用于趋势，避免无快照时
            # 把 0 当成真实结果。覆盖率口径固定为知识库切片索引覆盖率。
            knowledge_index_coverage_rate = MetricsUtil.calculate_knowledge_index_coverage_rate(db)
            learning_blind_spot_coverage_rate = MetricsUtil.calculate_learning_blind_spot_coverage_rate(db)
            resource_match_accuracy = db.query(func.avg(LearningResource.match_score)).scalar()
            resource_match_accuracy = (
                round(float(resource_match_accuracy), 2)
                if resource_match_accuracy is not None
                else None
            )

            trends = []
            for metric in reversed(metrics):
                detailed = metric.detailed_metrics or {}
                trends.append({
                    "date": metric.record_date,
                    "hallucination_rate": metric.hallucination_rate,
                    "resource_match_accuracy": metric.resource_match_accuracy,
                    "knowledge_coverage_rate": detailed.get(
                        "knowledge_index_coverage_rate",
                        metric.knowledge_coverage_rate,
                    ),
                })

            return {
                "hallucination_rate": hallucination_metrics["hallucination_rate"],
                "total_checks": hallucination_metrics["total_checks"],
                "evaluated_checks": hallucination_metrics["evaluated_checks"],
                "pending_checks": hallucination_metrics["pending_checks"],
                "confirmed_hallucinations": hallucination_metrics["confirmed_hallucinations"],
                "evidence_gaps": hallucination_metrics["evidence_gaps"],
                "pass_rate": hallucination_metrics["pass_rate"],
                "has_sufficient_sample": hallucination_metrics["has_sufficient_sample"],
                "minimum_sample_size": hallucination_metrics["minimum_sample_size"],
                "resource_match_accuracy": resource_match_accuracy,
                "knowledge_coverage_rate": knowledge_index_coverage_rate,
                "knowledge_index_coverage_rate": knowledge_index_coverage_rate,
                "learning_blind_spot_coverage_rate": learning_blind_spot_coverage_rate,
                "metrics_status": "ready" if knowledge_index_coverage_rate is not None else "no_data",
                "metrics_source": "realtime",
                "snapshot_available": bool(metrics),
                "calculated_at": utcnow_naive().isoformat(),
                "total_learners": learner_count,
                "total_resources": resource_count,
                "total_answers": answer_count,
                "active_sessions": 0,
                "avg_completion_time": "-",
                "satisfaction_score": 0,
                "trends": trends,
            }
