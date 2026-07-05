"""
企业培训服务单元测试
测试范围：CRUD、列表过滤分页、统计聚合、转岗、技能差距、批量导入
"""
import pytest
from sqlalchemy.orm import Session

from app.services.training_service import TrainingService
from app.schemas.training import (
    TrainingCreate,
    TrainingUpdate,
    TrainingBatchImportRequest,
    TrainingBatchImportItem,
)
from app.models.enterprise_training import EnterpriseTraining


def _make_training(db: Session, **overrides) -> EnterpriseTraining:
    """直接构造 EnterpriseTraining 记录，用于测试准备"""
    defaults = dict(
        company_name="测试企业",
        training_name="测试培训",
        training_type="standard",
        modules=["基础", "进阶"],
        participant_count=10,
        responsible_person="张三",
        status="planning",
        progress_percentage=0.0,
        completed_modules=0,
        is_transfer_training=False,
        pass_rate=0.0,
        average_score=0.0,
        satisfaction_rate=0.0,
    )
    defaults.update(overrides)
    t = EnterpriseTraining(**defaults)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


class TestTrainingCRUD:
    def test_create_training_sets_defaults(self, db_session: Session):
        data = TrainingCreate(
            company_name="某企业",
            training_name="Python 培训",
            training_type="standard",
            modules=["语法", "进阶"],
            participant_count=20,
        )
        t = TrainingService.create_training(db_session, data)
        assert t.id is not None
        assert t.status == "planning"
        assert t.progress_percentage == 0.0
        assert t.completed_modules == 0

    def test_get_training_by_id_returns_response(self, db_session: Session):
        created = _make_training(db_session, company_name="X 公司", training_name="X 培训")
        resp = TrainingService.get_training_by_id(db_session, created.id)
        assert resp is not None
        assert resp.id == created.id
        assert resp.company_name == "X 公司"
        assert resp.modules == ["基础", "进阶"]

    def test_get_training_by_id_returns_none_when_missing(self, db_session: Session):
        assert TrainingService.get_training_by_id(db_session, 99999) is None

    def test_delete_training_returns_true(self, db_session: Session):
        t = _make_training(db_session)
        assert TrainingService.delete_training(db_session, t.id) is True
        assert TrainingService.get_training_by_id(db_session, t.id) is None

    def test_delete_training_returns_false_when_missing(self, db_session: Session):
        assert TrainingService.delete_training(db_session, 99999) is False


class TestTrainingList:
    def test_list_returns_all_without_filter(self, db_session: Session):
        _make_training(db_session, company_name="甲", training_name="A")
        _make_training(db_session, company_name="乙", training_name="B")
        items, total = TrainingService.get_training_list(db_session, page=1, page_size=10)
        assert total == 2
        assert len(items) == 2

    def test_list_keyword_matches_company_or_training_name(self, db_session: Session):
        _make_training(db_session, company_name="甲企业", training_name="Java")
        _make_training(db_session, company_name="乙企业", training_name="Python")
        items, total = TrainingService.get_training_list(db_session, keyword="Python")
        assert total == 1
        assert items[0].training_name == "Python"

        items, total = TrainingService.get_training_list(db_session, keyword="甲")
        assert total == 1
        assert items[0].company_name == "甲企业"

    def test_list_status_filter(self, db_session: Session):
        _make_training(db_session, training_name="进行中", status="ongoing")
        _make_training(db_session, training_name="已完成", status="completed")
        items, total = TrainingService.get_training_list(db_session, status="ongoing")
        assert total == 1
        assert items[0].status == "ongoing"

    def test_list_pagination(self, db_session: Session):
        for i in range(5):
            _make_training(db_session, training_name=f"T{i}")
        items, total = TrainingService.get_training_list(db_session, page=2, page_size=2)
        assert total == 5
        assert len(items) == 2


class TestTrainingUpdate:
    def test_update_modifies_fields(self, db_session: Session):
        t = _make_training(db_session, training_name="原名")
        updated = TrainingService.update_training(
            db_session, t.id, TrainingUpdate(training_name="新名", status="ongoing")
        )
        assert updated is not None
        assert updated.training_name == "新名"
        assert updated.status == "ongoing"

    def test_update_returns_none_when_missing(self, db_session: Session):
        assert TrainingService.update_training(db_session, 99999, TrainingUpdate(status="ongoing")) is None

    def test_update_auto_syncs_completed_modules(self, db_session: Session):
        # 4 个模块，进度 50% → completed_modules = min(int(4*50/100), 4) = 2
        t = _make_training(
            db_session,
            modules=["m1", "m2", "m3", "m4"],
            progress_percentage=0.0,
        )
        updated = TrainingService.update_training(
            db_session, t.id, TrainingUpdate(progress_percentage=50.0)
        )
        assert updated.completed_modules == 2

    def test_update_completed_modules_capped_at_total(self, db_session: Session):
        # 2 个模块，进度 100% → min(int(2*100/100), 2) = 2
        t = _make_training(db_session, modules=["m1", "m2"], progress_percentage=0.0)
        updated = TrainingService.update_training(
            db_session, t.id, TrainingUpdate(progress_percentage=100.0)
        )
        assert updated.completed_modules == 2

    def test_update_does_not_sync_when_progress_zero(self, db_session: Session):
        t = _make_training(db_session, modules=["m1", "m2"], progress_percentage=0.0, completed_modules=0)
        updated = TrainingService.update_training(
            db_session, t.id, TrainingUpdate(training_name="改名")
        )
        # progress 仍为 0，不应触发同步
        assert updated.completed_modules == 0


class TestTrainingStats:
    def test_stats_counts_and_aggregations(self, db_session: Session):
        _make_training(db_session, company_name="甲", status="ongoing", participant_count=10, pass_rate=80.0, average_score=85.0)
        _make_training(db_session, company_name="甲", status="completed", participant_count=20, pass_rate=90.0, average_score=90.0)
        _make_training(db_session, company_name="乙", status="planning", participant_count=5, pass_rate=0.0, average_score=0.0)

        stats = TrainingService.get_stats(db_session)
        assert stats.total_trainings == 3
        assert stats.ongoing_trainings == 1
        assert stats.completed_trainings == 1
        assert stats.companies == 2
        assert stats.learners == 35
        # avg_pass 仅统计 pass_rate > 0 的：[80, 90] → 85.0
        assert stats.pass_rate == 85.0
        # avg_score 仅统计 average_score > 0 的：[85, 90] → 87.5
        assert stats.avg_score == 87.5

    def test_stats_empty_db_returns_zeros(self, db_session: Session):
        stats = TrainingService.get_stats(db_session)
        assert stats.total_trainings == 0
        assert stats.learners == 0
        assert stats.pass_rate == 0.0
        assert stats.avg_score == 0.0


class TestTransfers:
    def test_get_transfers_filters_and_maps_fields(self, db_session: Session):
        _make_training(
            db_session,
            is_transfer_training=True,
            responsible_person="李四",
            transfer_from_position="前端",
            transfer_to_position="后端",
            company_name="转岗公司",
            progress_percentage=60.0,
            skill_gap_analysis={"overall_gap": 25},
        )
        _make_training(db_session, is_transfer_training=False, responsible_person="不出现")
        transfers = TrainingService.get_transfers(db_session)
        assert len(transfers) == 1
        t = transfers[0]
        assert t["name"] == "李四"
        assert t["from"] == "前端"
        assert t["to"] == "后端"
        assert t["company"] == "转岗公司"
        assert t["completion"] == 60.0
        assert t["skill_gap"] == 25

    def test_get_transfers_empty_when_none(self, db_session: Session):
        _make_training(db_session, is_transfer_training=False)
        assert TrainingService.get_transfers(db_session) == []


class TestSkillGaps:
    def test_skill_gaps_aggregates_and_averages(self, db_session: Session):
        _make_training(
            db_session,
            is_transfer_training=True,
            skill_gap_analysis={"skills": [
                {"skill": "Python", "current": 60, "required": 80},
            ]},
        )
        _make_training(
            db_session,
            is_transfer_training=True,
            skill_gap_analysis={"skills": [
                {"skill": "Python", "current": 70, "required": 90},
                {"skill": "SQL", "current": 50, "required": 70},
            ]},
        )
        gaps = TrainingService.get_skill_gaps(db_session)
        by_skill = {g["skill"]: g for g in gaps}
        # Python: current avg=(60+70)/2=65, required avg=(80+90)/2=85, gap=20
        assert by_skill["Python"]["current"] == 65.0
        assert by_skill["Python"]["required"] == 85.0
        assert by_skill["Python"]["gap"] == 20.0
        # SQL: 单条，current=50, required=70, gap=20
        assert by_skill["SQL"]["current"] == 50.0
        assert by_skill["SQL"]["required"] == 70.0
        assert by_skill["SQL"]["gap"] == 20.0

    def test_skill_gaps_gap_never_negative(self, db_session: Session):
        _make_training(
            db_session,
            is_transfer_training=True,
            skill_gap_analysis={"skills": [
                {"skill": "已达标技能", "current": 90, "required": 70},
            ]},
        )
        gaps = TrainingService.get_skill_gaps(db_session)
        assert gaps[0]["gap"] == 0.0

    def test_skill_gaps_empty_when_no_analysis(self, db_session: Session):
        _make_training(db_session, is_transfer_training=True, skill_gap_analysis={})
        assert TrainingService.get_skill_gaps(db_session) == []


class TestBatchImport:
    def test_batch_import_counts_success(self, db_session: Session):
        req = TrainingBatchImportRequest(trainings=[
            TrainingBatchImportItem(company_name="甲", training_name="T1", participant_count=10),
            TrainingBatchImportItem(company_name="乙", training_name="T2", participant_count=20),
        ])
        result = TrainingService.batch_import(db_session, req)
        assert result["success_count"] == 2
        assert result["failed_count"] == 0
        assert TrainingService.get_stats(db_session).total_trainings == 2

    def test_batch_import_empty_list(self, db_session: Session):
        req = TrainingBatchImportRequest(trainings=[])
        result = TrainingService.batch_import(db_session, req)
        assert result["success_count"] == 0
        assert result["failed_count"] == 0
