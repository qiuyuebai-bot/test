"""
公共工具服务层
统一模型转换、数据库查询、日志记录等公共方法，消除各服务层重复代码
"""
import json
import time
import threading
from typing import Dict, Any, List, Optional, Type, TypeVar

from app.database import get_db_context
from app.models import (
    LearnerProfile,
    LearningResource,
    TestMetrics,
)
from app.utils.logger import LoggerUtil
from app.constants import MAX_DIFFICULTY

T = TypeVar('T')


class BaseService:
    """
    服务基类
    提供公共的模型转换、数据库查询、日志记录等方法
    所有Service类应继承此类
    """
    
    # 资源类型映射
    RESOURCE_TYPE_NAMES = {
        "guide": "实操指南",
        "exercise": "分阶测试题",
        "lecture": "专属知识讲义",
    }
    
    # 能力维度配置
    ABILITY_DIMENSIONS = [
        ("theoretical_foundation", "理论基础"),
        ("programming_ability", "编程能力"),
        ("algorithm_design", "算法设计"),
        ("system_architecture", "系统架构"),
        ("data_analysis", "数据分析"),
        ("engineering_practice", "工程实践"),
    ]
    
    # 缓存配置
    _cache: Dict[str, Any] = {}
    _cache_ttl: int = 300  # 缓存TTL: 5分钟
    _cache_lock: threading.Lock = threading.Lock()
    
    @classmethod
    def model_to_dict(cls, model) -> Dict[str, Any]:
        """
        ORM模型转字典（通用方法）
        
        Args:
            model: SQLAlchemy模型实例
            
        Returns:
            模型字段字典
        """
        if model is None:
            return {}
        
        result = {}
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            # 处理datetime等特殊类型
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    @classmethod
    def model_to_dict_safe(cls, model, fields: List[str] = None) -> Dict[str, Any]:
        """
        ORM模型转字典（安全版本，仅返回指定字段）
        
        Args:
            model: SQLAlchemy模型实例
            fields: 要返回的字段列表
            
        Returns:
            模型字段字典
        """
        if model is None:
            return {}
        
        if fields is None:
            return cls.model_to_dict(model)
        
        result = {}
        for field in fields:
            if hasattr(model, field):
                value = getattr(model, field)
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                result[field] = value
        return result
    
    @classmethod
    def parse_json_field(cls, value: str, default=None) -> Any:
        """
        安全解析JSON字段
        
        Args:
            value: JSON字符串
            default: 默认值
            
        Returns:
            解析后的对象
        """
        if not value:
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    
    @classmethod
    def get_by_id(cls, db, model_class: Type[T], id: int) -> Optional[T]:
        """
        根据ID获取单条记录
        
        Args:
            db: 数据库会话
            model_class: 模型类
            id: 记录ID
            
        Returns:
            模型实例或None
        """
        return db.query(model_class).filter(model_class.id == id).first()
    
    @classmethod
    def get_learner(cls, learner_id: int) -> Optional[LearnerProfile]:
        """
        根据ID获取学习者
        
        Args:
            learner_id: 学习者ID
            
        Returns:
            学习者对象或None
        """
        with get_db_context() as db:
            return cls.get_by_id(db, LearnerProfile, learner_id)
    
    @classmethod
    def get_learner_dict(cls, learner_id: int) -> Dict[str, Any]:
        """
        获取学习者字典（便捷方法）
        
        Args:
            learner_id: 学习者ID
            
        Returns:
            学习者字段字典
        """
        learner = cls.get_learner(learner_id)
        return cls.model_to_dict(learner) if learner else {}
    
    @classmethod
    def paginate_query(
        cls,
        db,
        query,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        分页查询工具
        
        Args:
            db: 数据库会话
            query: SQLAlchemy查询对象
            page: 页码（从1开始）
            page_size: 每页大小
            
        Returns:
            包含items和pagination的分页结果
        """
        total = query.count()
        offset = (max(1, page) - 1) * page_size
        items = query.offset(offset).limit(page_size).all()
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }
    
    @classmethod
    def log_request(
        cls,
        service_name: str,
        action: str,
        params: Dict[str, Any] = None,
    ) -> None:
        """
        记录API请求日志（便捷方法）
        
        Args:
            service_name: 服务名称
            action: 操作名称
            params: 请求参数
        """
        LoggerUtil.log_api_request(
            f"{service_name}.{action}",
            params or {},
        )
    
    @classmethod
    def log_error(
        cls,
        message: str,
        error: Exception = None,
    ) -> None:
        """
        记录错误日志（便捷方法）
        
        Args:
            message: 错误消息
            error: 异常对象
        """
        LoggerUtil.log_error(message, error)
    
    @classmethod
    def get_cache(cls, key: str) -> Optional[Any]:
        """
        获取缓存（线程安全）

        Args:
            key: 缓存键

        Returns:
            缓存值或None
        """
        with cls._cache_lock:
            if key in cls._cache:
                entry = cls._cache[key]
                if time.time() - entry["timestamp"] < cls._cache_ttl:
                    return entry["value"]
                else:
                    del cls._cache[key]
        return None

    @classmethod
    def set_cache(cls, key: str, value: Any) -> None:
        """
        设置缓存（线程安全）

        Args:
            key: 缓存键
            value: 缓存值
        """
        with cls._cache_lock:
            cls._cache[key] = {
                "value": value,
                "timestamp": time.time(),
            }

    @classmethod
    def clear_cache(cls, pattern: str = None) -> None:
        """
        清除缓存（线程安全）

        Args:
            pattern: 缓存键前缀（可选），为None时清除所有
        """
        with cls._cache_lock:
            if pattern is None:
                cls._cache.clear()
            else:
                cls._cache = {
                    k: v for k, v in cls._cache.items()
                    if not k.startswith(pattern)
                }


class LearnerServiceHelper(BaseService):
    """
    学习者相关公共方法
    """
    
    @classmethod
    def get_learner_ability_scores(cls, learner: LearnerProfile) -> Dict[str, float]:
        """
        获取学习者能力评分字典
        
        Args:
            learner: 学习者对象
            
        Returns:
            能力评分字典
        """
        scores = {}
        for field_key, _ in cls.ABILITY_DIMENSIONS:
            scores[field_key] = getattr(learner, field_key, 0) or 0
        return scores
    
    @classmethod
    def get_learner_average_ability(cls, learner: LearnerProfile) -> float:
        """
        获取学习者平均能力
        
        Args:
            learner: 学习者对象
            
        Returns:
            平均能力分数
        """
        scores = cls.get_learner_ability_scores(learner)
        return sum(scores.values()) / len(scores) if scores else 0
    
    @classmethod
    def get_learner_blind_areas(cls, learner: LearnerProfile) -> List[str]:
        """
        获取学习者知识盲区列表
        
        Args:
            learner: 学习者对象
            
        Returns:
            盲区列表
        """
        return learner.knowledge_blind_areas or []


class ResourceServiceHelper(BaseService):
    """
    资源相关公共方法
    """
    
    @classmethod
    def format_resource(cls, resource: LearningResource) -> Dict[str, Any]:
        """
        格式化资源数据
        
        Args:
            resource: 资源对象
            
        Returns:
            格式化后的资源字典
        """
        return {
            "resource_id": resource.id,
            "title": resource.title,
            "resource_type": resource.resource_type,
            "resource_type_name": cls.RESOURCE_TYPE_NAMES.get(
                resource.resource_type, resource.resource_type
            ),
            "difficulty_level": resource.difficulty_level,
            "knowledge_topic": resource.knowledge_topic,
            "word_count": resource.word_count,
            "match_score": resource.match_score,
            "validation_score": resource.validation_score,
            "status": resource.status,
            "view_count": resource.view_count or 0,
            "download_count": resource.download_count or 0,
            "created_at": resource.created_at.isoformat() if resource.created_at else None,
        }
    
    @classmethod
    def format_resource_detail(cls, resource: LearningResource) -> Dict[str, Any]:
        """
        格式化资源详情数据
        
        Args:
            resource: 资源对象
            
        Returns:
            格式化后的资源详情字典
        """
        result = cls.format_resource(resource)
        result.update({
            "learner_id": resource.learner_id,
            "content": resource.content,
            "content_json": cls.parse_json_field(resource.content_json, {}),
            "source_slice_ids": cls.parse_json_field(resource.source_slice_ids, []),
            "source_doc_ids": cls.parse_json_field(resource.source_doc_ids, []),
        })
        return result
    
    @classmethod
    def calculate_match_score(
        cls,
        recommended_difficulty: int,
        resource_difficulty: int,
        ability_scores: Dict[str, float],
        blind_areas: List[str],
        resource_content: str,
    ) -> float:
        """
        计算资源匹配度（通用方法）
        
        权重分配：
        - 难度匹配: 40%
        - 能力适配: 30%
        - 盲区覆盖: 30%
        
        Args:
            recommended_difficulty: 推荐难度
            resource_difficulty: 资源难度
            ability_scores: 能力评分字典
            blind_areas: 盲区列表
            resource_content: 资源内容
            
        Returns:
            匹配度分数(0-100)
        """
        score = 0
        
        # 1. 难度匹配分数（权重40%）
        diff_diff = abs(recommended_difficulty - resource_difficulty)
        difficulty_score = max(0, 100 - diff_diff * 20)
        score += difficulty_score * 0.4
        
        # 2. 能力适配分数（权重30%）
        avg_ability = sum(ability_scores.values()) / len(ability_scores) if ability_scores else 50
        expected_diff = min(MAX_DIFFICULTY, max(1, round(avg_ability / 20)))
        ability_diff = abs(expected_diff - resource_difficulty)
        ability_score = max(0, 100 - ability_diff * 25)
        score += ability_score * 0.3
        
        # 3. 盲区覆盖分数（权重30%）
        covered = sum(1 for b in blind_areas if b and b in resource_content)
        coverage_rate = covered / len(blind_areas) if blind_areas else 0.5
        coverage_score = coverage_rate * 100
        score += coverage_score * 0.3
        
        return round(score, 2)


class MetricsServiceHelper(BaseService):
    """
    指标统计公共方法
    """
    
    @classmethod
    def get_or_create_daily_metrics(cls, db) -> TestMetrics:
        """
        获取或创建当天的指标记录
        
        Args:
            db: 数据库会话
            
        Returns:
            指标记录
        """
        from datetime import date
        today = date.today()
        
        metrics = db.query(TestMetrics).filter(
            TestMetrics.record_date == today
        ).first()
        
        if not metrics:
            metrics = TestMetrics(
                record_date=today,
                record_period="daily",
            )
            db.add(metrics)
            db.flush()
        
        return metrics
    
    @classmethod
    def init_metrics_fields(cls, metrics: TestMetrics) -> None:
        """
        初始化指标字段（处理None值）
        
        Args:
            metrics: 指标记录
        """
        fields = [
            "total_match_attempts", "successful_match_count",
            "average_match_score", "total_resources_generated",
            "hallucination_rate", "resource_match_accuracy",
            "knowledge_coverage_rate",
        ]
        for field in fields:
            if getattr(metrics, field) is None:
                setattr(metrics, field, 0)
    
    @classmethod
    def update_match_metrics(
        cls,
        metrics: TestMetrics,
        match_score: float,
        resource_count: int,
    ) -> None:
        """
        更新资源匹配指标
        
        Args:
            metrics: 指标记录
            match_score: 匹配分数
            resource_count: 资源数量
        """
        cls.init_metrics_fields(metrics)
        
        metrics.total_match_attempts += 1
        if match_score >= 70:
            metrics.successful_match_count += 1
        
        # 移动平均
        metrics.average_match_score = (
            metrics.average_match_score * 0.7 + match_score * 0.3
        )
        metrics.total_resources_generated += resource_count
