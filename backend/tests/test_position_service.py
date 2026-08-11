"""Position 域 Service 单元测试"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.domains.position.schemas import PositionCreate, PositionUpdate, CompetencyCreate, CompetencyUpdate, PositionCompetencyCreate, PositionCompetencyUpdate
from app.domains.position.service import PositionService


@pytest.fixture
def db():
    """内存 SQLite 测试数据库"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCompetencyService:
    def test_create_competency(self, db):
        data = CompetencyCreate(code="PROG-PY", name="Python编程", category="technical")
        result = PositionService.create_competency(db, data)
        assert result["code"] == 200
        assert result["data"]["code"] == "PROG-PY"
        assert result["data"]["name"] == "Python编程"

    def test_create_duplicate_competency(self, db):
        data = CompetencyCreate(code="PROG-PY", name="Python编程")
        PositionService.create_competency(db, data)
        result = PositionService.create_competency(db, data)
        assert result["code"] == 400

    def test_get_competency_list(self, db):
        PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        PositionService.create_competency(db, CompetencyCreate(code="C2", name="技能2"))
        result = PositionService.get_competency_list(db, page=1, page_size=10)
        assert result["code"] == 200
        assert result["data"]["total"] == 2

    def test_update_competency(self, db):
        create_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="旧名称"))
        cid = create_result["data"]["id"]
        result = PositionService.update_competency(db, cid, CompetencyUpdate(name="新名称"))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"

    def test_delete_competency(self, db):
        create_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        cid = create_result["data"]["id"]
        result = PositionService.delete_competency(db, cid)
        assert result["code"] == 200


class TestPositionService:
    def test_create_position(self, db):
        data = PositionCreate(code="FE-001", name="前端工程师", category="technical", level="junior")
        result = PositionService.create_position(db, data)
        assert result["code"] == 200
        assert result["data"]["code"] == "FE-001"

    def test_get_position_list(self, db):
        PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        PositionService.create_position(db, PositionCreate(code="P2", name="岗位2"))
        result = PositionService.get_position_list(db, page=1, page_size=10)
        assert result["data"]["total"] == 2

    def test_get_position_list_with_filter(self, db):
        PositionService.create_position(db, PositionCreate(code="P1", name="前端", category="technical"))
        PositionService.create_position(db, PositionCreate(code="P2", name="产品", category="management"))
        result = PositionService.get_position_list(db, page=1, page_size=10, category="technical")
        assert result["data"]["total"] == 1

    def test_get_position_detail(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        pid = create_result["data"]["id"]
        result = PositionService.get_position_by_id(db, pid)
        assert result["code"] == 200
        assert result["data"]["name"] == "岗位1"
        assert result["data"]["competencies"] == []

    def test_update_position(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="旧名称"))
        pid = create_result["data"]["id"]
        result = PositionService.update_position(db, pid, PositionUpdate(name="新名称"))
        assert result["code"] == 200
        assert result["data"]["name"] == "新名称"

    def test_delete_position(self, db):
        create_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        pid = create_result["data"]["id"]
        result = PositionService.delete_position(db, pid)
        assert result["code"] == 200


class TestPositionCompetencyService:
    def test_add_competency_to_position(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]
        result = PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        assert result["code"] == 200
        assert result["data"]["required_level"] == 3

    def test_add_duplicate_competency(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]
        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=4
        ))
        assert result["code"] == 400

    def test_update_position_competency(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]
        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.update_position_competency(db, pid, cid, PositionCompetencyUpdate(
            required_level=5, is_mandatory=False
        ))
        assert result["code"] == 200
        assert result["data"]["required_level"] == 5
        assert result["data"]["is_mandatory"] is False

    def test_remove_competency_from_position(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]
        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=3
        ))
        result = PositionService.remove_competency_from_position(db, pid, cid)
        assert result["code"] == 200

    def test_get_position_detail_with_competencies(self, db):
        pos_result = PositionService.create_position(db, PositionCreate(code="P1", name="岗位1"))
        comp_result = PositionService.create_competency(db, CompetencyCreate(code="C1", name="技能1"))
        pid = pos_result["data"]["id"]
        cid = comp_result["data"]["id"]
        PositionService.add_competency_to_position(db, pid, PositionCompetencyCreate(
            competency_id=cid, required_level=4
        ))
        result = PositionService.get_position_by_id(db, pid)
        assert result["code"] == 200
        assert len(result["data"]["competencies"]) == 1
        assert result["data"]["competencies"][0]["competency_name"] == "技能1"
        assert result["data"]["competencies"][0]["required_level"] == 4
