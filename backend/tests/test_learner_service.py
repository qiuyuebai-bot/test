"""
学习者画像服务层单元测试
测试范围：画像CRUD、学情分析、批量导入导出、数据脱敏
"""
import pytest
from sqlalchemy.orm import Session

from app.services.learner_service import LearnerService
from app.schemas.learner import (
    LearnerProfileCreate,
    LearnerProfileUpdate,
    LearnerBatchImportRequest,
    LearnerBatchImportItem,
    AnonymizeRequest,
    AnswerRecordCreate,
)
from app.models import (
    LearnerProfile,
    User,
    UserRoleEnum,
    AnonymizedData,
    AnswerRecord,
)


class TestLearnerProfileCRUD:
    """学习者画像 CRUD 测试"""

    def test_create_learner(self, db_session: Session, sample_user: User):
        """测试创建学习者画像"""
        data = LearnerProfileCreate(
            user_id=sample_user.id,
            real_name="新学习者",
            education_level="硕士",
            major="人工智能",
            graduation_year=2023,
            learning_style="visual",
            target_industry="人工智能训练",
        )
        profile = LearnerService.create_learner(db_session, data)
        
        assert profile is not None
        assert profile.real_name == "新学习者"
        assert profile.education_level == "硕士"

    def test_create_duplicate_learner(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试为已有画像的用户创建画像"""
        data = LearnerProfileCreate(
            user_id=sample_learner_profile.user_id,
            real_name="重复",
            education_level="本科",
            major="测试",
        )
        profile = LearnerService.create_learner(db_session, data)
        
        assert profile is None

    def test_get_learner_list(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试获取学习者列表"""
        profiles, total = LearnerService.get_learner_list(db_session, page=1, page_size=10)
        
        assert total >= 1
        assert any(p.id == sample_learner_profile.id for p in profiles)

    def test_get_learner_by_id(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试根据ID获取学习者"""
        profile = LearnerService.get_learner_by_id(db_session, sample_learner_profile.id)
        
        assert profile is not None
        assert profile.id == sample_learner_profile.id
        assert profile.real_name == sample_learner_profile.real_name

    def test_get_learner_not_found(self, db_session: Session):
        """测试获取不存在的学习者"""
        profile = LearnerService.get_learner_by_id(db_session, 99999)
        assert profile is None

    def test_update_learner(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试更新学习者画像"""
        update_data = LearnerProfileUpdate(
            real_name="更新后的姓名",
            preferred_difficulty=4,
            theoretical_foundation=85.0,
        )
        profile = LearnerService.update_learner(
            db_session, sample_learner_profile.id, update_data
        )
        
        assert profile is not None
        assert profile.real_name == "更新后的姓名"
        assert profile.preferred_difficulty == 4
        assert profile.theoretical_foundation == 85.0

    def test_delete_learner(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试删除学习者画像"""
        result = LearnerService.delete_learner(db_session, sample_learner_profile.id)
        
        assert result is True


class TestLearnerAnalysis:
    """学情分析测试"""

    def test_analyze_learning(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试学情分析"""
        analysis = LearnerService.analyze_learning(db_session, sample_learner_profile.id)
        
        assert analysis is not None
        assert analysis.strengths is not None
        assert analysis.blind_areas is not None

    def test_analyze_learning_not_found(self, db_session: Session):
        """测试分析不存在的学习者"""
        analysis = LearnerService.analyze_learning(db_session, 99999)
        assert analysis is None


class TestLearnerBatchOperations:
    """批量操作测试"""

    def test_batch_import(self, db_session: Session):
        """测试批量导入学习者"""
        # 创建测试用户
        users = []
        for i in range(3):
            user = User(
                username=f"batch_test_{i}",
                password_hash="hash",
                email=f"batch{i}@test.com",
                role=UserRoleEnum.LEARNER,
            )
            db_session.add(user)
            users.append(user)
        db_session.commit()
        for u in users:
            db_session.refresh(u)
        
        request = LearnerBatchImportRequest(
            items=[
                LearnerBatchImportItem(
                    user_id=users[0].id,
                    real_name="批导1",
                    education_level="本科",
                    major="计算机",
                    theoretical_foundation=70.0,
                ),
                LearnerBatchImportItem(
                    user_id=users[1].id,
                    real_name="批导2",
                    education_level="硕士",
                    major="软件工程",
                    programming_ability=80.0,
                ),
                LearnerBatchImportItem(
                    user_id=users[2].id,
                    real_name="批导3",
                    education_level="博士",
                    major="人工智能",
                    algorithm_design=90.0,
                ),
            ]
        )
        response = LearnerService.batch_import(db_session, request)
        
        assert response is not None
        assert response.success_count == 3
        assert response.failed_count == 0

    def test_batch_export(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试批量导出学习者"""
        from app.schemas.learner import LearnerBatchExportRequest
        
        request = LearnerBatchExportRequest(
            learner_ids=[sample_learner_profile.id],
            format="json",
            include_anonymized=False,
        )
        result = LearnerService.batch_export(db_session, request)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) >= 1


class TestLearnerAnonymize:
    """数据脱敏测试"""

    def test_anonymize_learner(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试学习者数据脱敏"""
        request = AnonymizeRequest(
            learner_id=sample_learner_profile.id,
            fields=["real_name", "current_position"],
        )
        result = LearnerService.anonymize_learner(db_session, request)
        
        assert result is not None

    def test_anonymize_not_found(self, db_session: Session):
        """测试脱敏不存在的学习者"""
        request = AnonymizeRequest(learner_id=99999, fields=["real_name"])
        result = LearnerService.anonymize_learner(db_session, request)
        assert result is None


class TestLearnerAnswerRecords:
    """答题记录测试"""

    def test_add_answer_record(self, db_session: Session, sample_user: User, sample_learner_profile: LearnerProfile):
        """测试添加答题记录"""
        data = AnswerRecordCreate(
            user_id=sample_user.id,
            learner_id=sample_learner_profile.id,
            question_type="single",
            question_topic="CNN基础",
            question_difficulty=3,
            question_content="CNN的全称是什么？",
            user_answer=["A"],
            correct_answer=["A"],
            result="correct",
            score=10.0,
            time_spent_ms=30000,
        )
        record = LearnerService.add_answer_record(db_session, data)
        
        assert record is not None
        assert record.result == "correct"
        assert record.score == 10.0

    def test_get_answer_records(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试获取答题记录"""
        records, total = LearnerService.get_answer_records(
            db_session, sample_learner_profile.id, page=1, page_size=10
        )
        
        assert isinstance(records, list)


class TestLearnerPermission:
    """数据权限测试"""

    def test_check_permission_self(self, db_session: Session, sample_user: User, sample_learner_profile: LearnerProfile):
        """测试学习者查看自己的数据"""
        has_permission = LearnerService.check_data_permission(
            db_session,
            sample_user.id,
            sample_learner_profile.id,
        )
        assert has_permission is True

    def test_check_permission_admin(self, db_session: Session, sample_admin_user: User, sample_learner_profile: LearnerProfile):
        """测试管理员查看任意数据"""
        has_permission = LearnerService.check_data_permission(
            db_session,
            sample_admin_user.id,
            sample_learner_profile.id,
        )
        assert has_permission is True

    def test_check_permission_other(self, db_session: Session, sample_learner_profile: LearnerProfile):
        """测试非管理员查看他人数据"""
        # 创建另一个用户
        other_user = User(
            username="other_user",
            password_hash="hash",
            email="other@test.com",
            role=UserRoleEnum.LEARNER,
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        
        has_permission = LearnerService.check_data_permission(
            db_session,
            other_user.id,
            sample_learner_profile.id,
        )
        assert has_permission is False


class TestLearnerProfileProperties:
    """学习者画像属性测试"""

    def test_average_ability(self, sample_learner_profile: LearnerProfile):
        """测试平均能力计算"""
        avg = sample_learner_profile.average_ability
        expected = (75 + 80 + 70 + 60 + 65 + 72) / 6
        assert abs(avg - expected) < 0.01

    def test_comprehensive_ability(self, sample_learner_profile: LearnerProfile):
        """测试综合能力计算"""
        comp = sample_learner_profile.comprehensive_ability
        assert comp > 0

    def test_ability_profile(self, sample_learner_profile: LearnerProfile):
        """测试能力画像字典"""
        profile = sample_learner_profile.ability_profile
        assert "theoretical_foundation" in profile
        assert "average" in profile
        assert "comprehensive" in profile

    def test_learning_phase_label(self, sample_learner_profile: LearnerProfile):
        """测试学习阶段标签"""
        label = sample_learner_profile.learning_phase_label
        assert label == "成长期"