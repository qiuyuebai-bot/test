"""
P2-11 / P2-22 / P2-23 / P3-10 修复验证测试

- P2-11: SSE q.get 改用 asyncio.to_thread 避免阻塞事件循环
- P2-22: delete_doc 调整为「先删向量后软删 DB」并新增补偿对账方法
- P2-23: orchestrator _running_tasks 所有读写移入锁内
- P3-10: knowledge_slice.metadata 列重命名为 slice_metadata
"""
import asyncio
import queue
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.models import KnowledgeDoc, KnowledgeSlice
from app.domains.knowledge.service import KnowledgeService


# ===========================================
# P2-11: SSE q.get 不阻塞事件循环
# ===========================================

class TestP2_11_SSENonBlocking:
    """验证 asyncio.to_thread(q.get, ...) 不阻塞事件循环"""

    @pytest.mark.asyncio
    async def test_to_thread_returns_queued_event(self):
        """asyncio.to_thread(q.get) 能正确读取队列事件"""
        q = queue.Queue(maxsize=10)
        q.put({"event": "test", "data": {"msg": "hello"}})

        event = await asyncio.to_thread(q.get, timeout=1.0)
        assert event == {"event": "test", "data": {"msg": "hello"}}

    @pytest.mark.asyncio
    async def test_to_thread_does_not_block_event_loop(self):
        """q.get 超时期间，事件循环仍能并发执行其他任务"""
        q = queue.Queue(maxsize=10)  # 空队列，get 会超时

        async def another_task():
            await asyncio.sleep(0.05)
            return "ran"

        loop = asyncio.get_event_loop()
        start = loop.time()

        results = await asyncio.gather(
            asyncio.to_thread(q.get, timeout=0.2),
            another_task(),
            return_exceptions=True,
        )

        elapsed = loop.time() - start

        # q.get 超时抛出 queue.Empty
        assert isinstance(results[0], queue.Empty)
        # another_task 在 q.get 阻塞期间成功执行（证明事件循环未被阻塞）
        assert results[1] == "ran"
        # 并发执行，总耗时接近 max(0.2, 0.05) 而非 0.2 + 0.05
        assert elapsed < 0.3

    @pytest.mark.asyncio
    async def test_to_thread_concurrent_tasks_run_during_block(self):
        """多个并发任务能在 q.get 阻塞期间同时执行"""
        q = queue.Queue(maxsize=10)

        async def short_task(n):
            await asyncio.sleep(0.01)
            return n * 2

        results = await asyncio.gather(
            asyncio.to_thread(q.get, timeout=0.1),
            *[short_task(i) for i in range(5)],
            return_exceptions=True,
        )

        assert isinstance(results[0], queue.Empty)
        for i, result in enumerate(results[1:], 0):
            assert result == i * 2


# ===========================================
# P2-22: 删文档时 DB 与 Chroma 一致性
# ===========================================

class TestP2_22_DeleteDocConsistency:
    """delete_doc 先删向量后软删 DB，并新增 reconcile_orphaned_vectors"""

    def test_delete_doc_succeeds_when_chroma_unavailable(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """Chroma 不可用（测试环境）时，delete_doc 仍能软删 DB"""
        result = KnowledgeService.delete_doc(db_session, sample_knowledge_doc.id)

        assert result is True
        db_session.refresh(sample_knowledge_doc)
        assert sample_knowledge_doc.is_enabled is False

    def test_delete_doc_nonexistent_returns_false(self, db_session: Session):
        """删除不存在的文档返回 False"""
        result = KnowledgeService.delete_doc(db_session, 99999)
        assert result is False

    def test_delete_doc_soft_deletes_db_when_vector_delete_fails(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """向量删除失败时，DB 仍软删以保证用户体验"""
        with patch(
            "app.domains.knowledge.service._CHROMA_AVAILABLE", True
        ), patch(
            "app.domains.knowledge.service._get_chroma_collection"
        ) as mock_get:
            mock_collection = MagicMock()
            mock_collection.delete.side_effect = Exception("Chroma connection error")
            mock_get.return_value = mock_collection

            result = KnowledgeService.delete_doc(db_session, sample_knowledge_doc.id)

        assert result is True
        db_session.refresh(sample_knowledge_doc)
        assert sample_knowledge_doc.is_enabled is False

    def test_delete_doc_calls_vector_delete_before_db_commit(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """验证执行顺序：先删向量，后 commit DB"""
        call_order = []

        with patch(
            "app.domains.knowledge.service._CHROMA_AVAILABLE", True
        ), patch(
            "app.domains.knowledge.service._get_chroma_collection"
        ) as mock_get:
            mock_collection = MagicMock()

            def track_vector_delete(**kwargs):
                call_order.append("vector_delete")

            mock_collection.delete.side_effect = track_vector_delete
            mock_get.return_value = mock_collection

            original_commit = db_session.commit

            def tracked_commit():
                call_order.append("db_commit")
                original_commit()

            with patch.object(db_session, "commit", side_effect=tracked_commit):
                KnowledgeService.delete_doc(db_session, sample_knowledge_doc.id)

        assert "vector_delete" in call_order
        assert "db_commit" in call_order
        assert call_order.index("vector_delete") < call_order.index("db_commit")

    def test_reconcile_returns_zero_when_chroma_unavailable(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """Chroma 不可用时，reconcile 返回零计数"""
        sample_knowledge_doc.is_enabled = False
        db_session.commit()

        result = KnowledgeService.reconcile_orphaned_vectors(db_session)

        assert result == {"scanned": 0, "cleaned": 0, "failed": 0}

    def test_reconcile_cleans_soft_deleted_docs(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """reconcile 重试删除已软删文档的残留向量"""
        sample_knowledge_doc.is_enabled = False
        db_session.commit()

        with patch(
            "app.domains.knowledge.service._CHROMA_AVAILABLE", True
        ), patch(
            "app.domains.knowledge.service._get_chroma_collection"
        ) as mock_get:
            mock_collection = MagicMock()
            mock_get.return_value = mock_collection

            result = KnowledgeService.reconcile_orphaned_vectors(db_session)

        assert result["scanned"] == 1
        assert result["cleaned"] == 1
        assert result["failed"] == 0
        mock_collection.delete.assert_called_once_with(where={"doc_id": str(sample_knowledge_doc.id)})

    def test_reconcile_counts_failures(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """reconcile 正确统计向量删除失败"""
        sample_knowledge_doc.is_enabled = False
        db_session.commit()

        with patch(
            "app.domains.knowledge.service._CHROMA_AVAILABLE", True
        ), patch(
            "app.domains.knowledge.service._get_chroma_collection"
        ) as mock_get:
            mock_collection = MagicMock()
            mock_collection.delete.side_effect = Exception("Connection refused")
            mock_get.return_value = mock_collection

            result = KnowledgeService.reconcile_orphaned_vectors(db_session)

        assert result["scanned"] == 1
        assert result["cleaned"] == 0
        assert result["failed"] == 1


# ===========================================
# P2-23: orchestrator _running_tasks 锁安全
# ===========================================

class TestP2_23_OrchestratorLockSafety:
    """验证 _running_tasks 所有读写在锁内"""

    def test_update_running_task_updates_fields(self):
        """_update_running_task 在锁内更新指定字段"""
        orch = AgentOrchestrator()
        task_id = 999901

        with orch._running_tasks_lock:
            orch._running_tasks[task_id] = {
                "stage": "init",
                "progress": 0,
                "logs": [],
            }

        try:
            orch._update_running_task(task_id, diagnosis_result={"score": 85})

            with orch._running_tasks_lock:
                cached = orch._running_tasks[task_id]
                assert cached["diagnosis_result"] == {"score": 85}
                assert cached["stage"] == "init"  # 原字段保留

            # 一次更新多个字段
            orch._update_running_task(
                task_id,
                knowledge_results=["doc1"],
                generation_result={"content": "test"},
            )

            with orch._running_tasks_lock:
                cached = orch._running_tasks[task_id]
                assert cached["knowledge_results"] == ["doc1"]
                assert cached["generation_result"] == {"content": "test"}
                assert cached["diagnosis_result"] == {"score": 85}
        finally:
            with orch._running_tasks_lock:
                orch._running_tasks.pop(task_id, None)

    def test_update_running_task_nonexistent_task_no_error(self):
        """更新不存在的任务静默忽略，不抛异常"""
        orch = AgentOrchestrator()

        # 不应抛异常
        orch._update_running_task(888801, some_field="value")

        with orch._running_tasks_lock:
            assert 888801 not in orch._running_tasks

    def test_get_task_status_from_cache(self):
        """get_task_status 在锁内构造并返回缓存数据"""
        orch = AgentOrchestrator()
        task_id = 777701

        with orch._running_tasks_lock:
            orch._running_tasks[task_id] = {
                "stage": "generation",
                "progress": 50,
                "logs": [{"stage": "init"}],
                "description": "生成中",
            }

        try:
            status = orch.get_task_status(task_id)

            assert status["source"] == "cache"
            assert status["stage"] == "generation"
            assert status["progress"] == 50
            assert status["description"] == "生成中"
            assert status["status"] == "running"
        finally:
            with orch._running_tasks_lock:
                orch._running_tasks.pop(task_id, None)

    def test_get_task_status_nonexistent_returns_error(self, db_session: Session):
        """查询不存在的任务返回错误标记"""
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db_context():
            try:
                yield db_session
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise

        with patch("app.agents.orchestrator.get_db_context", mock_get_db_context):
            orch = AgentOrchestrator()
            status = orch.get_task_status(666601)

        assert status.get("error") == "任务不存在"
        assert status["task_id"] == 666601

    def test_get_task_logs_returns_copy_from_cache(self):
        """get_task_logs 返回缓存日志的副本，外部修改不影响原数据"""
        orch = AgentOrchestrator()
        task_id = 555501
        original_logs = [{"stage": "init", "progress": 0}]

        with orch._running_tasks_lock:
            orch._running_tasks[task_id] = {
                "stage": "init",
                "progress": 0,
                "logs": original_logs,
            }

        try:
            returned = orch.get_task_logs(task_id)
            assert returned == original_logs

            # 修改返回值不影响缓存
            returned.append({"stage": "modified"})
            with orch._running_tasks_lock:
                assert orch._running_tasks[task_id]["logs"] == original_logs
        finally:
            with orch._running_tasks_lock:
                orch._running_tasks.pop(task_id, None)


# ===========================================
# P3-10: knowledge_slice.metadata 列重命名
# ===========================================

class TestP3_10_SliceMetadataColumnRename:
    """验证 DB 列名从 metadata 改为 slice_metadata"""

    def test_db_column_name_is_slice_metadata(self):
        """ORM 表定义中列名为 slice_metadata 而非 metadata"""
        column_names = [col.name for col in KnowledgeSlice.__table__.columns]

        assert "slice_metadata" in column_names
        assert "metadata" not in column_names

    def test_slice_metadata_attribute_writable(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """Python 属性 slice_metadata 可正常写入"""
        meta = {"source": "test", "chunk_size": 512}
        s = KnowledgeSlice(
            doc_id=sample_knowledge_doc.id,
            slice_index=0,
            slice_type="paragraph",
            content="测试切片内容",
            content_hash="hash_p3_10_a",
            word_count=10,
            is_indexed=False,
            slice_metadata=meta,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        assert s.slice_metadata == meta

    def test_slice_metadata_default_empty_dict(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """未指定 slice_metadata 时默认为空 dict"""
        s = KnowledgeSlice(
            doc_id=sample_knowledge_doc.id,
            slice_index=1,
            slice_type="paragraph",
            content="默认值测试",
            content_hash="hash_p3_10_b",
            word_count=5,
            is_indexed=False,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        assert s.slice_metadata == {}

    def test_slice_metadata_persisted_and_reloadable(
        self, db_session: Session, sample_knowledge_doc: KnowledgeDoc
    ):
        """slice_metadata 写入 DB 后能重新查询读取"""
        meta = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        s = KnowledgeSlice(
            doc_id=sample_knowledge_doc.id,
            slice_index=2,
            slice_type="section",
            content="持久化测试",
            content_hash="hash_p3_10_c",
            word_count=4,
            is_indexed=True,
            slice_metadata=meta,
        )
        db_session.add(s)
        db_session.commit()
        slice_id = s.id

        # 清除 ORM 身份映射，强制重新查询
        db_session.expire_all()
        retrieved = (
            db_session.query(KnowledgeSlice)
            .filter(KnowledgeSlice.id == slice_id)
            .first()
        )

        assert retrieved is not None
        assert retrieved.slice_metadata == meta
