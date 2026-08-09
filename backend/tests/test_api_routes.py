"""
API 路由集成测试
测试范围：核心接口端到端测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import IssuedTutoringQuestion, User, LearnerProfile, KnowledgeDoc, AnswerRecord
from app.services import tutoring_service as tutoring_service_module


class TestBaseRoutes:
    """基础路由测试"""

    def test_root(self, client: TestClient):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "running"

    def test_health_check(self, client: TestClient):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "alive"

    def test_system_info(self, client: TestClient):
        """测试系统信息"""
        response = client.get("/api/v1/info")
        assert response.status_code == 200
        data = response.json()
        assert "features" in data["data"]

    def test_core_metrics(self, client: TestClient):
        """测试核心指标"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "hallucination_rate" in data["data"]
        assert "resource_match_accuracy" in data["data"]


class TestLearnerRoutes:
    """学习者画像路由测试"""

    def test_create_learner(self, client: TestClient, sample_user: User, auth_headers: dict):
        """测试创建学习者"""
        response = client.post("/api/v1/learners", json={
            "user_id": sample_user.id,
            "real_name": "API测试",
            "education_level": "硕士",
            "major": "计算机科学",
            "learning_style": "visual",
            "target_industry": "人工智能训练",
            "theoretical_foundation": 75.0,
            "programming_ability": 80.0,
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_learner_list(self, client: TestClient, sample_learner_profile: LearnerProfile, admin_auth_headers: dict):
        """测试获取学习者列表"""
        response = client.get("/api/v1/learners?page=1&page_size=10", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"] or isinstance(data["data"], (list, dict))

    def test_get_current_learner(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        response = client.get("/api/v1/learners/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == sample_learner_profile.id
        assert data["data"]["user_id"] == sample_learner_profile.user_id

    def test_get_current_learner_requires_a_profile(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/learners/me", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["code"] == 404

    def test_get_learner_detail(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试获取学习者详情"""
        response = client.get(f"/api/v1/learners/{sample_learner_profile.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_learner_not_found(self, client: TestClient, auth_headers: dict):
        """测试获取不存在的学习者"""
        response = client.get("/api/v1/learners/99999", headers=auth_headers)
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404

    def test_update_learner(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试更新学习者"""
        response = client.put(f"/api/v1/learners/{sample_learner_profile.id}", json={
            "real_name": "更新名称",
            "preferred_difficulty": 4,
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_delete_learner(self, client: TestClient, sample_user: User, auth_headers: dict):
        """测试删除学习者"""
        # 先创建一个新学习者用于删除
        response = client.post("/api/v1/learners", json={
            "user_id": sample_user.id,
            "real_name": "待删除",
            "education_level": "本科",
            "major": "测试",
            "learning_style": "visual",
        }, headers=auth_headers)
        if response.status_code == 200:
            learner_id = response.json()["data"]["id"]
            delete_response = client.delete(f"/api/v1/learners/{learner_id}", headers=auth_headers)
            assert delete_response.status_code == 200

    def test_analyze_learning(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试学情分析"""
        response = client.post(f"/api/v1/learners/{sample_learner_profile.id}/analyze", headers=auth_headers)
        assert response.status_code in [200, 404]  # 可能返回404如果无答题记录

    def test_anonymize_learner(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试数据脱敏"""
        response = client.post(
            f"/api/v1/learners/{sample_learner_profile.id}/anonymize",
            json={"fields": ["real_name", "current_position"]},
            headers=auth_headers,
        )
        assert response.status_code == 200


class TestKnowledgeRoutes:
    """知识库路由测试"""

    def test_create_doc(self, client: TestClient, admin_auth_headers: dict):
        """测试创建知识库文档"""
        response = client.post("/api/v1/knowledge/upload", json={
            "title": "测试知识文档",
            "industry": "人工智能训练",
            "category": "深度学习",
            "description": "API测试文档",
            "source": "测试",
            "author": "测试者",
            "content": "这是一份测试文档内容，包含深度学习相关知识...",
        }, headers=admin_auth_headers)
        # Chroma 被测试 fixture 禁用时，上传必须明确报告索引不可用，不能伪装成成功。
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400
        assert "索引" in data["message"] or "Chroma" in data["message"]

    def test_get_doc_list(self, client: TestClient, sample_knowledge_doc: KnowledgeDoc, auth_headers: dict):
        """测试获取文档列表"""
        response = client.get("/api/v1/knowledge/docs?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_doc_detail(self, client: TestClient, sample_knowledge_doc: KnowledgeDoc, auth_headers: dict):
        """测试获取文档详情"""
        response = client.get(f"/api/v1/knowledge/docs/{sample_knowledge_doc.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_search_knowledge(self, client: TestClient, auth_headers: dict):
        """测试知识库检索"""
        response = client.post("/api/v1/knowledge/search", json={
            "query": "深度学习",
            "top_k": 5,
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_industry_stats(self, client: TestClient, auth_headers: dict):
        """测试行业统计"""
        response = client.get("/api/v1/knowledge/stats/industries", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestAgentRoutes:
    """Agent协同路由测试"""

    def test_get_agent_status(self, client: TestClient, auth_headers: dict):
        """测试获取Agent状态"""
        response = client.get("/api/v1/agent/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_agent_tasks(self, client: TestClient, auth_headers: dict):
        """测试获取Agent任务列表"""
        response = client.get("/api/v1/agent/tasks?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_diagnose(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试学情诊断"""
        response = client.post("/api/v1/agent/diagnose", json={
            "learner_id": sample_learner_profile.id,
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_metrics(self, client: TestClient, auth_headers: dict):
        """测试Agent指标"""
        response = client.get("/api/v1/agent/metrics/hallucination", headers=auth_headers)
        assert response.status_code == 200


class TestCoreRoutes:
    """核心业务路由测试"""

    def test_generate_resources(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试生成资源"""
        response = client.post("/api/v1/resources/generate/sync", json={
            "learner_id": sample_learner_profile.id,
            "target_topic": "CNN入门",
            "industry": "人工智能训练",
        }, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_resources(
        self,
        client: TestClient,
        auth_headers: dict,
        sample_learner_profile: LearnerProfile,
    ):
        """测试获取资源列表"""
        response = client.get("/api/v1/resources?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_report(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试获取学情报告"""
        response = client.get(f"/api/v1/report/learner/{sample_learner_profile.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_heatmap(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试获取知识盲区热力图"""
        response = client.get(f"/api/v1/report/heatmap/{sample_learner_profile.id}", headers=auth_headers)
        assert response.status_code == 200

    def test_get_match_curve(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试获取难度匹配曲线"""
        response = client.get(f"/api/v1/report/match-curve/{sample_learner_profile.id}", headers=auth_headers)
        assert response.status_code == 200

    def test_get_metrics(self, client: TestClient):
        """测试获取系统指标"""
        response = client.get("/api/v1/report/metrics")
        assert response.status_code == 200

    def test_submit_answer(self, client: TestClient, db_session: Session, sample_user: User, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试提交答题"""
        question = IssuedTutoringQuestion(
            user_id=sample_user.id,
            learner_id=sample_learner_profile.id,
            question_type="single",
            topic="CNN基础",
            difficulty=3,
            content="CNN的全称是什么？",
            options=["A", "B"],
            answer_key=["A"],
            explanation="CNN是卷积神经网络。",
            knowledge_points=["CNN"],
            generation_method="test",
            status="issued",
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        response = client.post("/api/v1/tutoring/answer", json={
            "user_id": sample_user.id,
            "learner_id": sample_learner_profile.id,
            "question_id": str(question.id),
            "question_type": "single",
            "question_topic": "CNN基础",
            "question_difficulty": 3,
            "question_content": "CNN的全称是什么？",
            "user_answer": ["A"],
            "correct_answer": ["A"],
            "result": "correct",
            "score": 10.0,
            "time_spent_ms": 30000,
            "session_id": "e2e-round-1",
            "sequence_index": 1,
        }, headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["score"] in {0, 100}
        assert "knowledge_expansion" in payload["generated_content"]
        record = db_session.query(AnswerRecord).filter(AnswerRecord.learner_id == sample_learner_profile.id).order_by(AnswerRecord.id.desc()).first()
        assert record is not None
        assert record.session_id == "e2e-round-1"
        assert record.sequence_index == 1

    def test_get_tutoring_history(self, client: TestClient, sample_learner_profile: LearnerProfile, auth_headers: dict):
        """测试获取交互历史"""
        response = client.get(f"/api/v1/tutoring/history/{sample_learner_profile.id}?page=1&page_size=10", headers=auth_headers)
        assert response.status_code == 200

    def test_delete_tutoring_history_record(
        self,
        client: TestClient,
        sample_learner_profile: LearnerProfile,
        sample_answer_record: AnswerRecord,
        auth_headers: dict,
    ):
        response = client.delete(
            f"/api/v1/tutoring/history/{sample_learner_profile.id}?record_id={sample_answer_record.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["deleted_count"] == 1

    def test_generate_tutoring_questions_normalizes_topic_and_hides_answer(
        self,
        client: TestClient,
        sample_learner_profile: LearnerProfile,
        auth_headers: dict,
        monkeypatch,
    ):
        monkeypatch.setattr(
            tutoring_service_module.LLMUtil,
            "is_available",
            classmethod(lambda cls: False),
        )
        monkeypatch.setattr(
            tutoring_service_module,
            "DiagnosisAgent",
            lambda: type(
                "FakeDiagnosis",
                (),
                {"execute": lambda self, payload: {"recommended_difficulty": {"recommended_difficulty": 2}}},
            )(),
        )

        response = client.post(
            "/api/v1/tutoring/questions/generate",
            json={
                "learner_id": sample_learner_profile.id,
                "topic": "BP算法",
                "difficulty": 2,
                "question_count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        question = response.json()["data"]["questions"][0]
        assert question["topic"] == "反向传播算法"
        assert "answer_key" not in question
        assert "correctAnswer" not in question

    def test_generate_tutoring_questions_accepts_custom_topic_and_count(
        self,
        client: TestClient,
        sample_learner_profile: LearnerProfile,
        auth_headers: dict,
        monkeypatch,
    ):
        monkeypatch.setattr(
            tutoring_service_module.LLMUtil,
            "is_available",
            classmethod(lambda cls: False),
        )
        monkeypatch.setattr(
            tutoring_service_module,
            "DiagnosisAgent",
            lambda: type(
                "FakeDiagnosis",
                (),
                {"execute": lambda self, payload: {"recommended_difficulty": {"recommended_difficulty": 3}}},
            )(),
        )

        response = client.post(
            "/api/v1/tutoring/questions/generate",
            json={
                "learner_id": sample_learner_profile.id,
                "topic": "REST API",
                "difficulty": 4,
                "question_count": 5,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        questions = response.json()["data"]["questions"]
        assert len(questions) == 5
        assert all(question["topic"] == "REST API" for question in questions)
        assert all(question["difficulty"] == 4 for question in questions)
        assert all("correctAnswer" not in question and "answer_key" not in question for question in questions)

    @pytest.mark.parametrize(
        "payload",
        [
            {"topic": "REST API", "difficulty": 0, "question_count": 3},
            {"topic": "REST API", "difficulty": 6, "question_count": 3},
            {"topic": "REST API", "difficulty": 3, "question_count": 0},
            {"topic": "REST API", "difficulty": 3, "question_count": 11},
        ],
    )
    def test_generate_tutoring_questions_rejects_invalid_bounds(
        self,
        client: TestClient,
        sample_learner_profile: LearnerProfile,
        auth_headers: dict,
        payload: dict,
    ):
        response = client.post(
            "/api/v1/tutoring/questions/generate",
            json={"learner_id": sample_learner_profile.id, **payload},
            headers=auth_headers,
        )

        assert response.status_code in (400, 422)


class TestErrorHandling:
    """错误处理测试"""

    def test_rejects_malformed_requests(self, client: TestClient, auth_headers: dict):
        """测试拒绝无效JSON和缺少必填字段的请求"""
        # 无效JSON
        response = client.post(
            "/api/v1/learners",
            content="invalid json {{{",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

        # 缺少必填字段
        response = client.post("/api/v1/learners", json={}, headers=auth_headers)
        assert response.status_code in [400, 422]

    def test_invalid_page_params(self, client: TestClient, admin_auth_headers: dict):
        """测试无效分页参数"""
        response = client.get("/api/v1/learners?page=-1&page_size=0", headers=admin_auth_headers)
        assert response.status_code in [200, 422]

    def test_404_not_found_route(self, client: TestClient):
        """测试不存在的路由"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
