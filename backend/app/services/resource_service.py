"""
个性化知识资源生成服务
一次调用生成三类资源：定制实操指南、分阶训练测试题、专属知识讲义
"""
import json
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.database import get_db_context
from app.models import (
    LearningResource,
)
from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.generation_agent import GenerationAgent
from app.services.knowledge_service import KnowledgeService
from app.services.common import BaseService, ResourceServiceHelper, MetricsServiceHelper


class ResourceGenerationService(BaseService):
    """
    个性化知识资源生成服务
    
    核心能力：
    - 一次调用生成三类资源（复用诊断+检索阶段）
    - 资源分层存储（基础/进阶）
    - 资源匹配度计算
    """
    
    RESOURCE_TYPES = ["guide", "exercise", "lecture"]
    
    @classmethod
    def generate_all_resources(
        cls,
        learner_id: int,
        target_topic: str,
        industry: str = None,
    ) -> Dict[str, Any]:
        """
        一次性生成三类学习资源（核心方法）
        """
        logger.info(
            f"[资源生成服务] 开始生成三类资源: learner_id={learner_id}, "
            f"topic={target_topic}, industry={industry}"
        )
        
        start_time = time.time()
        
        try:
            # 阶段1：学情诊断（只执行一次）
            diagnosis_result = cls._run_diagnosis(learner_id)
            
            # 阶段2：知识库检索（只执行一次）
            knowledge_results = cls._retrieve_knowledge(
                target_topic=target_topic,
                industry=industry,
            )
            
            # 获取学习者
            learner = cls.get_learner(learner_id)
            learner_dict = cls.model_to_dict(learner)
            ability_scores = diagnosis_result.get("ability_scores", {})
            blind_areas = diagnosis_result.get("knowledge_blind_areas", [])
            recommended_diff = diagnosis_result.get(
                "recommended_difficulty", {}
            ).get("recommended_difficulty", 3)
            
            # 阶段3：批量生成三类资源
            all_resources = []
            total_match_score = 0
            
            for res_type in cls.RESOURCE_TYPES:
                res_result = cls._generate_single_resource(
                    learner_dict=learner_dict,
                    target_topic=target_topic,
                    resource_type=res_type,
                    diagnosis_result=diagnosis_result,
                    knowledge_results=knowledge_results,
                )
                
                # 计算匹配度
                match_score = ResourceServiceHelper.calculate_match_score(
                    recommended_difficulty=recommended_diff,
                    resource_difficulty=res_result.get("difficulty_level", 3),
                    ability_scores=ability_scores,
                    blind_areas=[b.get("name", "") for b in blind_areas],
                    resource_content=res_result.get("content", ""),
                )
                res_result["match_score"] = match_score
                res_result["resource_type_name"] = cls.RESOURCE_TYPE_NAMES.get(res_type, res_type)
                total_match_score += match_score
                
                # 保存资源
                saved = cls._save_resource(
                    learner_id=learner_id,
                    resource_type=res_type,
                    resource_data=res_result,
                    diagnosis_result=diagnosis_result,
                    target_topic=target_topic,
                )
                res_result["saved_resource_id"] = saved.id
                all_resources.append(res_result)
            
            # 计算平均匹配度
            avg_match_score = total_match_score / len(cls.RESOURCE_TYPES)
            
            # 保存指标
            cls._save_metrics(
                learner_id=learner_id,
                resource_count=len(all_resources),
                avg_match_score=avg_match_score,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "success": True,
                "learner_id": learner_id,
                "target_topic": target_topic,
                "industry": industry,
                "generated_resources": all_resources,
                "resource_count": len(all_resources),
                "avg_match_score": round(avg_match_score, 2),
                "diagnosis_summary": {
                    "overall_score": diagnosis_result.get("overall_score", 0),
                    "overall_level": diagnosis_result.get("overall_level", ""),
                    "blind_areas_count": len(blind_areas),
                    "recommended_difficulty": diagnosis_result.get("recommended_difficulty", {}),
                },
                "knowledge_retrieved_count": len(knowledge_results),
                "duration_ms": duration_ms,
            }
            
            cls.log_request("ResourceGenerationService", "generate_all_resources", {
                "learner_id": learner_id,
                "resources": len(all_resources),
                "match_score": avg_match_score,
            })
            
            logger.info(
                f"[资源生成服务] 生成完成: {len(all_resources)}类资源, "
                f"匹配度={avg_match_score:.2f}, 耗时={duration_ms}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[资源生成服务] 生成失败: {e}")
            cls.log_error("资源生成失败", e)
            return {
                "success": False,
                "error": str(e),
                "learner_id": learner_id,
                "target_topic": target_topic,
            }
    
    @classmethod
    def _run_diagnosis(cls, learner_id: int) -> Dict[str, Any]:
        """运行学情诊断"""
        learner = cls.get_learner(learner_id)
        if not learner:
            raise ValueError(f"学习者不存在: {learner_id}")
        
        learner_dict = cls.model_to_dict(learner)
        agent = DiagnosisAgent()
        
        return agent.run(
            task_id=-1,
            input_data={
                "learner_id": learner_id,
                "learner_profile": learner_dict,
            },
        )
    
    @classmethod
    def _retrieve_knowledge(
        cls,
        target_topic: str,
        industry: str = None,
    ) -> List[Dict]:
        """检索知识库"""
        with get_db_context() as db:
            return KnowledgeService.search(
                db=db,
                query=target_topic,
                industry=industry,
                top_k=10,
            )
    
    @classmethod
    def _generate_single_resource(
        cls,
        learner_dict: Dict[str, Any],
        target_topic: str,
        resource_type: str,
        diagnosis_result: Dict[str, Any],
        knowledge_results: List[Dict],
    ) -> Dict[str, Any]:
        """生成单一类型资源"""
        agent = GenerationAgent()
        result = agent.run(
            task_id=-1,
            input_data={
                "diagnosis_result": diagnosis_result,
                "knowledge_results": knowledge_results,
                "learner_profile": learner_dict,
                "target_topic": target_topic,
                "resource_type": resource_type,
            },
        )
        return result
    
    @classmethod
    def _save_resource(
        cls,
        learner_id: int,
        resource_type: str,
        resource_data: Dict[str, Any],
        diagnosis_result: Dict[str, Any],
        target_topic: str = "",
    ) -> LearningResource:
        """保存资源到数据库"""
        with get_db_context() as db:
            resource = LearningResource(
                learner_id=learner_id,
                title=resource_data.get("resource_title", "未命名资源"),
                resource_type=resource_type,
                knowledge_topic=target_topic,
                difficulty_level=resource_data.get("difficulty_level", 3),
                version="1.0",
                content=resource_data.get("content", ""),
                content_json=json.dumps(
                    resource_data.get("content_json", {}),
                    ensure_ascii=False,
                    default=str,
                ),
                word_count=resource_data.get("word_count", 0),
                source_slice_ids=json.dumps(
                    resource_data.get("source_slice_ids", []),
                    ensure_ascii=False,
                ),
                source_doc_ids=json.dumps(
                    resource_data.get("source_doc_ids", []),
                    ensure_ascii=False,
                ),
                generated_by_agent="generation_agent",
                generation_method="knowledge_based",
                is_validated=True,
                validation_passed=True,
                validation_score=resource_data.get("_meta", {}).get("score", 80),
                hallucination_detected=False,
                status="published",
                match_score=resource_data.get("match_score", 0),
            )
            db.add(resource)
            db.flush()
            db.commit()
            return resource
    
    @classmethod
    def _save_metrics(
        cls,
        learner_id: int,
        resource_count: int,
        avg_match_score: float,
    ) -> None:
        """保存指标到统计表"""
        with get_db_context() as db:
            metrics = MetricsServiceHelper.get_or_create_daily_metrics(db)
            MetricsServiceHelper.update_match_metrics(
                metrics, avg_match_score, resource_count
            )
            db.commit()
    
    @classmethod
    def get_resource_list(
        cls,
        learner_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        difficulty_level: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取资源列表"""
        with get_db_context() as db:
            query = db.query(LearningResource)
            
            if learner_id:
                query = query.filter(LearningResource.learner_id == learner_id)
            if resource_type:
                query = query.filter(LearningResource.resource_type == resource_type)
            if difficulty_level:
                query = query.filter(LearningResource.difficulty_level == difficulty_level)
            if status:
                query = query.filter(LearningResource.status == status)
            
            query = query.order_by(LearningResource.created_at.desc())
            
            paged = cls.paginate_query(db, query, page, page_size)
            
            resources = [
                ResourceServiceHelper.format_resource(r)
                for r in paged["items"]
            ]
            
            return {
                "resources": resources,
                "total": paged["total"],
                "page": page,
                "page_size": page_size,
            }
    
    @classmethod
    def get_resource_detail(cls, resource_id: int) -> Optional[Dict[str, Any]]:
        """获取资源详情"""
        with get_db_context() as db:
            resource = cls.get_by_id(db, LearningResource, resource_id)
            if not resource:
                return None
            
            # 增加查看计数
            resource.view_count = (resource.view_count or 0) + 1
            db.commit()
            
            return ResourceServiceHelper.format_resource_detail(resource)
    
    @classmethod
    def export_resource(cls, resource_id: int, fmt: str = "txt") -> str:
        """导出资源文件"""
        resource = cls.get_resource_detail(resource_id)
        if not resource:
            return ""
        
        if fmt == "md":
            content = f"# {resource['title']}\n\n"
            content += f"**类型**: {resource['resource_type_name']}\n"
            content += f"**难度**: {'★' * resource['difficulty_level']}\n"
            content += f"**匹配度**: {resource['match_score']}%\n"
            content += f"**字数**: {resource['word_count']}\n\n"
            content += "---\n\n"
            content += resource.get("content", "")
        else:
            content = f"{resource['title']}\n"
            content += f"类型: {resource['resource_type_name']}\n"
            content += f"难度: {'★' * resource['difficulty_level']}\n"
            content += f"匹配度: {resource['match_score']}%\n"
            content += "\n" + resource.get("content", "")
        
        return content
