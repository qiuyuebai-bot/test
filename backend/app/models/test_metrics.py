"""
系统测试指标统计表 ORM 模型
存储系统核心量化指标数据
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON
from sqlalchemy.sql import func
from app.database import Base


class TestMetrics(Base):
    """系统测试指标统计表"""
    
    __tablename__ = "test_metrics"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="指标ID")
    
    # 时间维度
    record_date = Column(DateTime, nullable=False, index=True, comment="记录日期")
    record_period = Column(String(20), default="daily", comment="统计周期(daily/weekly/monthly)")
    
    # 三大核心量化指标
    hallucination_rate = Column(Float, default=0.0, comment="知识幻觉错误率(%)")
    resource_match_accuracy = Column(Float, default=0.0, comment="资源匹配准确率(%)")
    knowledge_coverage_rate = Column(Float, default=0.0, comment="知识点覆盖率(%)")
    
    # 幻觉检测详情
    total_generated_content = Column(Integer, default=0, comment="总生成内容数")
    hallucination_detected_count = Column(Integer, default=0, comment="幻觉检测数")
    hallucination_corrected_count = Column(Integer, default=0, comment="幻觉修正数")
    
    # 资源匹配详情
    total_match_attempts = Column(Integer, default=0, comment="总匹配尝试数")
    successful_match_count = Column(Integer, default=0, comment="成功匹配数")
    average_match_score = Column(Float, default=0.0, comment="平均匹配分数")
    
    # 知识覆盖详情
    total_knowledge_points = Column(Integer, default=0, comment="总知识点数")
    covered_knowledge_points = Column(Integer, default=0, comment="已覆盖知识点数")
    uncovered_knowledge_points = Column(Integer, default=0, comment="未覆盖知识点数")
    
    # Agent执行统计
    agent_task_count = Column(Integer, default=0, comment="Agent任务总数")
    agent_success_count = Column(Integer, default=0, comment="Agent成功数")
    agent_failure_count = Column(Integer, default=0, comment="Agent失败数")
    agent_avg_duration_ms = Column(Float, default=0.0, comment="Agent平均耗时(毫秒)")
    
    # Token消耗统计
    total_prompt_tokens = Column(Integer, default=0, comment="总Prompt Token")
    total_completion_tokens = Column(Integer, default=0, comment="总Completion Token")
    total_tokens = Column(Integer, default=0, comment="总Token消耗")
    
    # 学习者统计
    active_learner_count = Column(Integer, default=0, comment="活跃学习者数")
    new_learner_count = Column(Integer, default=0, comment="新增学习者数")
    
    # 资源统计
    total_resources_generated = Column(Integer, default=0, comment="生成资源总数")
    resources_by_type = Column(JSON, default=dict, comment="按类型资源统计")
    
    # 答题统计
    total_answers = Column(Integer, default=0, comment="总答题数")
    correct_answer_count = Column(Integer, default=0, comment="正确答题数")
    wrong_answer_count = Column(Integer, default=0, comment="错误答题数")
    average_answer_time_ms = Column(Float, default=0.0, comment="平均答题耗时")
    
    # 测试套件统计
    test_suite_count = Column(Integer, default=0, comment="测试套件数")
    test_case_count = Column(Integer, default=0, comment="测试用例数")
    test_pass_rate = Column(Float, default=0.0, comment="测试通过率")
    
    # 系统健康指标
    system_uptime_rate = Column(Float, default=100.0, comment="系统可用率(%)")
    api_response_time_ms = Column(Float, default=0.0, comment="API平均响应时间")
    error_count = Column(Integer, default=0, comment="错误数")
    
    # 详细指标数据（JSON）
    detailed_metrics = Column(JSON, default=dict, comment="详细指标数据")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self) -> str:
        return f"<TestMetrics(id={self.id}, date={self.record_date}, hallucination={self.hallucination_rate}%)>"