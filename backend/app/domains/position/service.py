"""
岗位与胜任力域 Service 层
"""
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.domains.position.models import Position, Competency, PositionCompetency
from app.domains.position.schemas import (
    PositionCreate, PositionUpdate,
    CompetencyCreate, CompetencyUpdate,
    PositionCompetencyCreate, PositionCompetencyUpdate,
)
from app.schemas.response import (
    success as _success,
    bad_request as _bad_request,
    not_found as _not_found,
)


def _unwrap(resp) -> Dict[str, Any]:
    """将 JSONResponse 解包为 dict（service 层返回 dict，与 Dict[str, Any] 类型注解一致）"""
    return json.loads(resp.body)


# 包装响应函数：复用统一响应构造逻辑，但返回 dict 便于 service 层链式处理与单元测试断言
def success(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    return _unwrap(_success(data=data, message=message))


def bad_request(message: str = "请求参数错误", data: Any = None) -> Dict[str, Any]:
    return _unwrap(_bad_request(message=message, data=data))


def not_found(message: str = "资源不存在") -> Dict[str, Any]:
    return _unwrap(_not_found(message=message))


class PositionService:
    """岗位与胜任力服务"""

    # ===========================================
    # Competency CRUD
    # ===========================================

    @staticmethod
    def create_competency(db: Session, data: CompetencyCreate) -> Dict[str, Any]:
        existing = db.query(Competency).filter(Competency.code == data.code).first()
        if existing:
            return bad_request(message=f"胜任力编码已存在: {data.code}")
        comp = Competency(
            code=data.code,
            name=data.name,
            category=data.category,
            description=data.description,
            level_descriptions=data.level_descriptions or {},
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)
        return success(data=PositionService._competency_to_response(comp), message="胜任力创建成功")

    @staticmethod
    def get_competency_list(
        db: Session, page: int = 1, page_size: int = 20,
        keyword: Optional[str] = None, category: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(Competency)
        if keyword:
            query = query.filter(or_(
                Competency.name.contains(keyword),
                Competency.code.contains(keyword),
            ))
        if category:
            query = query.filter(Competency.category == category)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [PositionService._competency_to_response(c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_competency_by_id(db: Session, competency_id: int) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        return success(data=PositionService._competency_to_response(comp))

    @staticmethod
    def update_competency(db: Session, competency_id: int, data: CompetencyUpdate) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(comp, key, value)
        db.commit()
        db.refresh(comp)
        return success(data=PositionService._competency_to_response(comp), message="更新成功")

    @staticmethod
    def delete_competency(db: Session, competency_id: int) -> Dict[str, Any]:
        comp = db.query(Competency).filter(Competency.id == competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        db.delete(comp)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # Position CRUD
    # ===========================================

    @staticmethod
    def create_position(db: Session, data: PositionCreate) -> Dict[str, Any]:
        existing = db.query(Position).filter(Position.code == data.code).first()
        if existing:
            return bad_request(message=f"岗位编码已存在: {data.code}")
        pos = Position(
            code=data.code,
            name=data.name,
            category=data.category,
            industry=data.industry,
            level=data.level,
            description=data.description,
            responsibilities=data.responsibilities or [],
            key_tasks=data.key_tasks or [],
            prerequisites=data.prerequisites or [],
            career_path=data.career_path or [],
        )
        db.add(pos)
        db.commit()
        db.refresh(pos)
        return success(data=PositionService._position_to_response(pos), message="岗位创建成功")

    @staticmethod
    def get_position_list(
        db: Session, page: int = 1, page_size: int = 20,
        keyword: Optional[str] = None, category: Optional[str] = None,
        industry: Optional[str] = None, level: Optional[str] = None
    ) -> Dict[str, Any]:
        query = db.query(Position)
        if keyword:
            query = query.filter(or_(
                Position.name.contains(keyword),
                Position.code.contains(keyword),
            ))
        if category:
            query = query.filter(Position.category == category)
        if industry:
            query = query.filter(Position.industry == industry)
        if level:
            query = query.filter(Position.level == level)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return success(data={
            "items": [PositionService._position_to_response(p) for p in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        })

    @staticmethod
    def get_position_by_id(db: Session, position_id: int) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        return success(data=PositionService._position_detail_to_response(pos))

    @staticmethod
    def update_position(db: Session, position_id: int, data: PositionUpdate) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pos, key, value)
        db.commit()
        db.refresh(pos)
        return success(data=PositionService._position_to_response(pos), message="更新成功")

    @staticmethod
    def delete_position(db: Session, position_id: int) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        db.delete(pos)
        db.commit()
        return success(message="删除成功")

    # ===========================================
    # Position-Competency 关联管理
    # ===========================================

    @staticmethod
    def add_competency_to_position(
        db: Session, position_id: int, data: PositionCompetencyCreate
    ) -> Dict[str, Any]:
        pos = db.query(Position).filter(Position.id == position_id).first()
        if not pos:
            return not_found(message="岗位不存在")
        comp = db.query(Competency).filter(Competency.id == data.competency_id).first()
        if not comp:
            return not_found(message="胜任力不存在")
        existing = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == data.competency_id,
        ).first()
        if existing:
            return bad_request(message="该胜任力已关联到此岗位")

        pc = PositionCompetency(
            position_id=position_id,
            competency_id=data.competency_id,
            required_level=data.required_level,
            weight=data.weight,
            is_mandatory=data.is_mandatory,
        )
        db.add(pc)
        db.commit()
        db.refresh(pc)
        return success(data=PositionService._pc_to_response(pc), message="胜任力已添加到岗位")

    @staticmethod
    def update_position_competency(
        db: Session, position_id: int, competency_id: int, data: PositionCompetencyUpdate
    ) -> Dict[str, Any]:
        pc = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == competency_id,
        ).first()
        if not pc:
            return not_found(message="岗位胜任力关联不存在")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pc, key, value)
        db.commit()
        db.refresh(pc)
        return success(data=PositionService._pc_to_response(pc), message="更新成功")

    @staticmethod
    def remove_competency_from_position(
        db: Session, position_id: int, competency_id: int
    ) -> Dict[str, Any]:
        pc = db.query(PositionCompetency).filter(
            PositionCompetency.position_id == position_id,
            PositionCompetency.competency_id == competency_id,
        ).first()
        if not pc:
            return not_found(message="岗位胜任力关联不存在")
        db.delete(pc)
        db.commit()
        return success(message="已移除胜任力")

    # ===========================================
    # 私有转换方法
    # ===========================================

    @staticmethod
    def _competency_to_response(comp: Competency) -> Dict[str, Any]:
        return {
            "id": comp.id,
            "code": comp.code,
            "name": comp.name,
            "category": comp.category,
            "description": comp.description,
            "level_descriptions": comp.level_descriptions,
            "is_active": comp.is_active,
            "created_at": comp.created_at.isoformat() if comp.created_at else None,
            "updated_at": comp.updated_at.isoformat() if comp.updated_at else None,
        }

    @staticmethod
    def _position_to_response(pos: Position) -> Dict[str, Any]:
        return {
            "id": pos.id,
            "code": pos.code,
            "name": pos.name,
            "category": pos.category,
            "industry": pos.industry,
            "level": pos.level,
            "description": pos.description,
            "responsibilities": pos.responsibilities,
            "key_tasks": pos.key_tasks or [],
            "prerequisites": pos.prerequisites,
            "career_path": pos.career_path,
            "is_active": pos.is_active,
            "created_at": pos.created_at.isoformat() if pos.created_at else None,
            "updated_at": pos.updated_at.isoformat() if pos.updated_at else None,
        }

    @staticmethod
    def _position_detail_to_response(pos: Position) -> Dict[str, Any]:
        result = PositionService._position_to_response(pos)
        result["competencies"] = [
            PositionService._pc_to_response(pc) for pc in pos.competencies
        ]
        return result

    @staticmethod
    def _pc_to_response(pc: PositionCompetency) -> Dict[str, Any]:
        return {
            "id": pc.id,
            "position_id": pc.position_id,
            "competency_id": pc.competency_id,
            "competency_name": pc.competency.name if pc.competency else None,
            "competency_code": pc.competency.code if pc.competency else None,
            "competency_category": pc.competency.category if pc.competency else None,
            "required_level": pc.required_level,
            "weight": pc.weight,
            "is_mandatory": pc.is_mandatory,
            "created_at": pc.created_at.isoformat() if pc.created_at else None,
        }
