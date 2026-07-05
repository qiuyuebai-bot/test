#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化测试数据脚本
一键导入评审使用的测试数据集：知识库切片 + 学习者样例 + 资源模板 + 演示资源
"""
import sys
import os
import json
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_database
from app.models import (
    KnowledgeDoc,
    KnowledgeSlice,
    LearnerProfile,
    User,
    UserRoleEnum,
    LearningResource,
    ResourceSection,
    ResourceExercise,
    ResourceTemplate,
    ResourceMedia,
    TestMetrics,
    AgentTask,
    AnswerRecord,
)
from app.utils.text_slice import TextSliceUtil
from loguru import logger


# ===========================================
# 测试知识库内容
# ===========================================

TEST_KNOWLEDGE_DOCS = [
    {
        "title": "智能制造系统架构设计",
        "industry": "智能制造",
        "category": "系统架构",
        "source": "内部培训教材",
        "author": "张三",
        "tags": ["智能制造", "系统架构", "MES", "工业互联网"],
        "content": """
# 智能制造系统架构设计

## 第一章 智能制造概述

智能制造是基于新一代信息通信技术与先进制造技术深度融合，贯穿于设计、生产、管理、服务等制造活动的各个环节，具有自感知、自学习、自决策、自执行、自适应等功能的新型生产方式。

### 1.1 智能制造的核心特征

智能制造系统具有以下核心特征：

- **自感知**：通过传感器、物联网等技术，实现对生产过程、设备、产品的全面感知
- **自决策**：基于大数据分析和人工智能技术，实现生产过程的智能决策
- **自执行**：通过智能装备、智能生产线等实现生产过程的自动化执行
- **自适应**：能够根据外部环境变化和内部状态变化，自动调整系统运行状态

### 1.2 智能制造的技术体系

智能制造的技术体系包括：

1. 感知与识别技术
2. 网络与通信技术
3. 大数据与云计算技术
4. 人工智能技术
5. 自动化与机器人技术

## 第二章 MES系统核心功能

制造执行系统（MES）是面向车间层的生产管理技术与实时信息系统。

### 2.1 MES系统架构

MES系统通常由以下模块组成：

- 生产计划与调度
- 质量管理
- 设备管理
- 物料管理
- 工艺管理
- 人员管理

### 2.2 MES与ERP的关系

ERP关注企业级的资源规划，MES关注车间级的生产执行。

## 第三章 工业互联网平台

工业互联网平台是面向制造业数字化、网络化、智能化的关键支撑。

### 3.1 平台架构

工业互联网平台通常包括：

- 边缘层
- IaaS层
- PaaS层
- SaaS层

### 3.2 关键技术

包括：

- 大数据技术
- 云计算技术
- 人工智能技术
- 数字孪生技术
""",
    },
    {
        "title": "工业互联网数据采集与处理",
        "industry": "工业互联网",
        "category": "数据采集",
        "source": "技术文档",
        "author": "李四",
        "tags": ["工业互联网", "数据采集", "边缘计算", "MQTT"],
        "content": """
# 工业互联网数据采集与处理技术

## 第一章 数据采集技术

工业互联网数据采集是工业互联网平台的基础，负责从各种工业设备、传感器、控制系统等采集数据。

### 1.1 数据采集方式

常见的数据采集方式包括：

- **直接采集**：通过接口直连设备，直接读取设备数据
- **网关采集**：通过工业网关进行协议转换后采集
- **系统对接**：与MES、ERP等系统对接获取数据
- **人工录入**：通过人工方式录入数据

### 1.2 工业协议

常用的工业协议包括：

1. Modbus协议
2. OPC UA协议
3. MQTT协议
4. Profibus协议
5. EtherNet/IP协议

## 第二章 边缘计算

边缘计算是在靠近数据源头的一侧进行计算，提供实时数据处理能力。

### 2.1 边缘计算架构

边缘计算架构包括：

- 边缘设备层
- 边缘网关层
- 边缘平台层

### 2.2 边缘计算优势

- 低延迟
- 带宽节省
- 数据安全
- 可靠性高

## 第三章 数据处理技术

### 3.1 流处理技术

流处理技术用于处理实时数据流。

### 3.2 批处理技术

批处理技术用于处理批量数据处理。
""",
    },
    {
        "title": "Python高级编程实战",
        "industry": "软件开发",
        "category": "编程语言",
        "source": "编程教材",
        "author": "王五",
        "tags": ["Python", "高级编程", "设计模式", "并发编程"],
        "content": """
# Python高级编程实战指南

## 第一章 面向对象编程

### 1.1 类与对象

Python是面向对象的编程语言，支持类、继承、多态等面向对象特性。

```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def introduce(self):
        print(f"我叫{self.name}，今年{self.age}岁")
```

### 1.2 继承与多态

```python
class Student(Person):
    def __init__(self, name, age, grade):
        super().__init__(name, age)
        self.grade = grade
    
    def introduce(self):
        super().introduce()
        print(f"我是{self.grade}年级学生")
```

## 第二章 设计模式

### 2.1 单例模式

确保一个类只有一个实例。

### 2.2 工厂模式

通过工厂方法创建对象。

### 2.3 观察者模式

对象之间一对多的依赖关系。

## 第三章 并发编程

### 3.1 多线程

使用threading模块实现多线程。

### 3.2 多进程

使用multiprocessing模块实现多进程。

### 3.3 异步编程

使用asyncio实现异步编程。

## 第四章 性能优化

### 4.1 代码优化

### 4.2 内存优化

### 4.3 IO优化
""",
    },
    {
        "title": "深度学习基础到进阶",
        "industry": "人工智能训练",
        "category": "深度学习",
        "source": "AI培训",
        "author": "赵六",
        "tags": ["深度学习", "神经网络", "PyTorch", "CNN", "Transformer"],
        "content": """
# 深度学习从基础到进阶

## 第一章 深度学习基础

### 1.1 神经网络基础

神经网络是深度学习的基础，由神经元、层、网络组成。

### 1.2 激活函数

常见的激活函数：

- ReLU
- Sigmoid
- Tanh
- Softmax

### 1.3 损失函数

- MSE均方误差
- 交叉熵损失

## 第二章 卷积神经网络

### 2.1 CNN基本结构

卷积层、池化层、全连接层。

### 2.2 经典CNN模型

- LeNet
- AlexNet
- VGG
- ResNet

## 第三章 Transformer架构

### 3.1 注意力机制

自注意力机制是Transformer的核心。

### 3.2 Transformer结构

编码器-解码器架构。

### 3.3 BERT模型

双向编码器表示。

## 第四章 模型训练

### 4.1 优化器

- SGD
- Adam
- RMSprop

### 4.2 学习率调度

### 4.3 正则化

Dropout、权重衰减等。
""",
    },
]


# ===========================================
# 测试学习者样例
# ===========================================

TEST_LEARNERS = [
    {
        "real_name": "张明远",
        "education_level": "硕士",
        "major": "机械工程",
        "graduation_year": 2020,
        "current_position": "工艺工程师",
        "learning_style": "visual",
        "preferred_difficulty": 3,
        "daily_study_time": 90,
        "target_industry": "智能制造",
        "target_position": "智能制造工程师",
        "learning_goal": "掌握智能制造系统设计与工业互联网技术，实现职业转型",
        "theoretical_foundation": 72.0,
        "programming_ability": 45.0,
        "algorithm_design": 55.0,
        "system_architecture": 60.0,
        "data_analysis": 68.0,
        "engineering_practice": 80.0,
        "knowledge_blind_areas": ["Python编程", "机器学习算法", "工业互联网架构", "数据采集"],
    },
    {
        "real_name": "李雨晴",
        "education_level": "本科",
        "major": "计算机科学",
        "graduation_year": 2022,
        "current_position": "初级开发工程师",
        "learning_style": "reading",
        "preferred_difficulty": 2,
        "daily_study_time": 60,
        "target_industry": "软件开发",
        "target_position": "高级后端工程师",
        "learning_goal": "提升编程能力与系统设计水平",
        "theoretical_foundation": 65.0,
        "programming_ability": 70.0,
        "algorithm_design": 60.0,
        "system_architecture": 50.0,
        "data_analysis": 55.0,
        "engineering_practice": 72.0,
        "knowledge_blind_areas": ["系统架构设计", "微服务", "高并发", "性能优化"],
    },
    {
        "real_name": "王浩宇",
        "education_level": "博士",
        "major": "人工智能",
        "graduation_year": 2023,
        "current_position": "AI算法工程师",
        "learning_style": "kinesthetic",
        "preferred_difficulty": 5,
        "daily_study_time": 120,
        "target_industry": "人工智能训练",
        "target_position": "AI架构师",
        "learning_goal": "深入研究大模型与多智能体协同技术",
        "theoretical_foundation": 92.0,
        "programming_ability": 88.0,
        "algorithm_design": 95.0,
        "system_architecture": 78.0,
        "data_analysis": 90.0,
        "engineering_practice": 85.0,
        "knowledge_blind_areas": ["多智能体强化学习", "大模型对齐", "Prompt Engineering"],
    },
    {
        "real_name": "陈思雨",
        "education_level": "本科",
        "major": "自动化",
        "graduation_year": 2021,
        "current_position": "运维工程师",
        "learning_style": "visual",
        "preferred_difficulty": 2,
        "daily_study_time": 45,
        "target_industry": "工业互联网",
        "target_position": "DevOps工程师",
        "learning_goal": "向DevOps方向转型，提升云原生技能",
        "theoretical_foundation": 58.0,
        "programming_ability": 50.0,
        "algorithm_design": 40.0,
        "system_architecture": 55.0,
        "data_analysis": 48.0,
        "engineering_practice": 75.0,
        "knowledge_blind_areas": ["Python编程", "容器技术", "CI/CD", "监控告警"],
    },
]


def init_knowledge_docs(db):
    """初始化知识库文档"""
    logger.info("开始初始化知识库测试数据...")
    
    for doc_data in TEST_KNOWLEDGE_DOCS:
        # 创建文档记录
        doc = KnowledgeDoc(
            title=doc_data["title"],
            industry=doc_data["industry"],
            category=doc_data["category"],
            file_name=f"{doc_data['title']}.md",
            file_path=f"./data/knowledge_docs/test.md",
            file_size=len(doc_data["content"].encode("utf-8")),
            file_type="md",
            source=doc_data["source"],
            author=doc_data["author"],
            tags=doc_data["tags"],
            word_count=len(doc_data["content"]),
            status="ready",
            process_progress=100,
        )
        db.add(doc)
        db.flush()
        
        # 文本切片
        slices = TextSliceUtil.slice_by_paragraph(
            doc_data["content"],
            max_chunk_size=400,
            overlap=30,
        )
        doc.slice_count = len(slices)
        doc.indexed_slice_count = len(slices)
        
        # 存储切片
        for slice_data in slices:
            slice_obj = KnowledgeSlice(
                doc_id=doc.id,
                slice_index=slice_data["slice_index"],
                slice_type=slice_data["slice_type"],
                title=slice_data.get("title", ""),
                content=slice_data["content"],
                content_hash=slice_data["content_hash"],
                word_count=slice_data["word_count"],
                keywords=slice_data.get("keywords", []),
                context_before=slice_data.get("context_before", ""),
                context_after=slice_data.get("context_after", ""),
                is_indexed=True,
                quality_score=0.85,
                reference_count=0,
            )
            db.add(slice_obj)
    
    db.commit()
    logger.info(f"知识库初始化完成: {len(TEST_KNOWLEDGE_DOCS)} 个文档")


def init_learners(db):
    """初始化学习者测试数据"""
    logger.info("开始初始化学习者测试数据...")
    
    # 创建测试用户
    users = []
    for i, learner_data in enumerate(TEST_LEARNERS):
        user = User(
            username=f"test_user_{i+1}",
            password_hash="hashed_password_test",
            email=f"user{i+1}@test.com",
            role=UserRoleEnum.LEARNER,
            is_active=True,
        )
        db.add(user)
        users.append(user)
    
    db.flush()
    
    # 创建学习者画像
    for i, learner_data in enumerate(TEST_LEARNERS):
        learner = LearnerProfile(
            user_id=users[i].id,
            real_name=learner_data["real_name"],
            education_level=learner_data["education_level"],
            major=learner_data["major"],
            graduation_year=learner_data["graduation_year"],
            current_position=learner_data["current_position"],
            learning_style=learner_data["learning_style"],
            preferred_difficulty=learner_data["preferred_difficulty"],
            daily_study_time=learner_data["daily_study_time"],
            target_industry=learner_data["target_industry"],
            target_position=learner_data["target_position"],
            learning_goal=learner_data["learning_goal"],
            theoretical_foundation=learner_data["theoretical_foundation"],
            programming_ability=learner_data["programming_ability"],
            algorithm_design=learner_data["algorithm_design"],
            system_architecture=learner_data["system_architecture"],
            data_analysis=learner_data["data_analysis"],
            engineering_practice=learner_data["engineering_practice"],
            knowledge_blind_areas=learner_data["knowledge_blind_areas"],
            is_data_anonymized=False,
        )
        db.add(learner)
    
    db.commit()
    logger.info(f"学习者初始化完成: {len(TEST_LEARNERS)} 个学习者")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始初始化测试数据")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 初始化数据库表
        init_database()
        
        # 初始化知识库
        init_knowledge_docs(db)
        
        # 初始化学习者
        init_learners(db)
        
        logger.info("=" * 60)
        logger.info("测试数据初始化完成！")
        logger.info("=" * 60)
        
        # 统计
        doc_count = db.query(KnowledgeDoc).count()
        slice_count = db.query(KnowledgeSlice).count()
        learner_count = db.query(LearnerProfile).count()
        
        logger.info(f"知识库文档: {doc_count} 个")
        logger.info(f"知识切片: {slice_count} 个")
        logger.info(f"学习者: {learner_count} 个")
        
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()