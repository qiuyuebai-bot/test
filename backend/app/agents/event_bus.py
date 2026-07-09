"""
任务事件总线（SSE 实时推送）

两种实现：
- TaskEventBus: 进程内发布/订阅（默认，daemon 线程模式，无需 Redis）
- RedisTaskEventBus: 基于 Redis pub/sub 的跨进程事件总线（Celery worker → web 进程 SSE）

通过 create_event_bus() 工厂按 settings.USE_CELERY 自动选择。
"""
import json
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger


class TaskEventBus:
    """线程安全的进程内任务事件发布/订阅"""

    def __init__(self, max_queue_size: int = 200):
        self._subscribers: Dict[int, List[queue.Queue]] = {}
        self._subscribers_lock = threading.Lock()
        self._max_queue_size = max_queue_size

    def broadcast(self, task_id: int, event_type: str, data: Dict[str, Any]) -> None:
        """向指定任务的所有订阅者广播事件"""
        event = {"event": event_type, "data": data}
        with self._subscribers_lock:
            subscribers = self._subscribers.get(task_id, [])
            dead_queues = []
            for q in subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead_queues.append(q)
            for q in dead_queues:
                subscribers.remove(q)

    def subscribe(self, task_id: int) -> queue.Queue:
        """订阅任务事件，返回事件队列"""
        q: queue.Queue = queue.Queue(maxsize=self._max_queue_size)
        with self._subscribers_lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(q)
        return q

    def unsubscribe(self, task_id: int, q: queue.Queue) -> None:
        """取消订阅"""
        with self._subscribers_lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    def cleanup(self, task_id: int) -> None:
        """清理指定任务的所有订阅者"""
        with self._subscribers_lock:
            self._subscribers.pop(task_id, None)

    @staticmethod
    def build_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """构造标准事件结构"""
        return {"event": event_type, "data": {**data, "timestamp": data.get("timestamp", time.time())}}


class RedisTaskEventBus:
    """
    基于 Redis pub/sub 的跨进程事件总线

    用于 Celery worker（发布）↔ web 进程（订阅）的 SSE 桥接：
    - broadcast() 在 Celery worker 中执行，PUBLISH 到 Redis channel
    - subscribe() 在 web 进程中执行，启动后台线程 SUBSCRIBE 并转发到 queue.Queue
    - SSE 端点从 queue.Queue 消费，代码与进程内模式完全一致

    channel 命名: task_events:{task_id}
    """

    _CHANNEL_PREFIX = "task_events:"

    def __init__(self, redis_url: str, max_queue_size: int = 200):
        self._redis_url = redis_url
        self._max_queue_size = max_queue_size
        self._subscribers: Dict[int, List[_RedisSubscription]] = {}
        self._subscribers_lock = threading.Lock()

    def _get_redis(self):
        import redis
        return redis.Redis.from_url(self._redis_url, decode_responses=True)

    def broadcast(self, task_id: int, event_type: str, data: Dict[str, Any]) -> None:
        """在 Celery worker 进程中执行：PUBLISH 事件到 Redis channel"""
        event = {"event": event_type, "data": data}
        try:
            client = self._get_redis()
            client.publish(
                f"{self._CHANNEL_PREFIX}{task_id}",
                json.dumps(event, ensure_ascii=False, default=str),
            )
            client.close()
        except Exception as e:
            logger.warning(f"[RedisEventBus] 发布失败（Redis 不可用，事件丢失）: task_id={task_id}, error={e}")

    def subscribe(self, task_id: int) -> "_RedisSubscription":
        """在 web 进程中执行：启动后台线程订阅 Redis channel，转发到 queue.Queue"""
        sub = _RedisSubscription(
            redis_url=self._redis_url,
            channel=f"{self._CHANNEL_PREFIX}{task_id}",
            max_queue_size=self._max_queue_size,
        )
        with self._subscribers_lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(sub)
        sub.start()
        return sub

    def unsubscribe(self, task_id: int, sub: "_RedisSubscription") -> None:
        """取消订阅，停止后台线程"""
        sub.stop()
        with self._subscribers_lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(sub)
                except ValueError:
                    pass
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    def cleanup(self, task_id: int) -> None:
        """清理指定任务的所有订阅者"""
        with self._subscribers_lock:
            subs = self._subscribers.pop(task_id, [])
        for sub in subs:
            sub.stop()

    @staticmethod
    def build_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"event": event_type, "data": {**data, "timestamp": data.get("timestamp", time.time())}}


class _RedisSubscription:
    """
    Redis 订阅包装器：后台线程读 Redis pubsub → queue.Queue

    暴露与 queue.Queue 兼容的接口（get_nowait / get / put_nowait），
    使 SSE 端点代码无需区分进程内/Redis 模式。
    """

    def __init__(self, redis_url: str, channel: str, max_queue_size: int = 200):
        self._redis_url = redis_url
        self._channel = channel
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._listen, name=f"redis-sub-{self._channel}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _listen(self) -> None:
        import redis
        try:
            client = redis.Redis.from_url(self._redis_url, decode_responses=True)
            pubsub = client.pubsub()
            pubsub.subscribe(self._channel)
            while not self._stop_event.is_set():
                msg = pubsub.get_message(timeout=1.0)
                if msg and msg.get("type") == "message":
                    try:
                        event = json.loads(msg["data"])
                        try:
                            self._queue.put_nowait(event)
                        except queue.Full:
                            pass
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"[RedisSub] 解析事件失败: {e}")
            try:
                pubsub.unsubscribe(self._channel)
                pubsub.close()
            except Exception:
                pass
            client.close()
        except Exception as e:
            logger.error(f"[RedisSub] 订阅线程异常（channel={self._channel}）: {e}")

    def get_nowait(self):
        return self._queue.get_nowait()

    def get(self, timeout: Optional[float] = None):
        return self._queue.get(timeout=timeout)

    def put_nowait(self, item):
        self._queue.put_nowait(item)

    def empty(self) -> bool:
        return self._queue.empty()


def create_event_bus(max_queue_size: int = 200):
    """
    事件总线工厂：按 settings.USE_CELERY 选择实现

    - USE_CELERY=false（默认）: 返回 TaskEventBus（进程内，无需 Redis）
    - USE_CELERY=true: 返回 RedisTaskEventBus（跨进程，需 Redis 可达）

    两者接口完全一致（broadcast/subscribe/unsubscribe/cleanup/build_event）。
    """
    from app.config import settings

    if settings.USE_CELERY:
        logger.info("[EventBus] 使用 RedisTaskEventBus（Celery 跨进程模式）")
        return RedisTaskEventBus(redis_url=settings.REDIS_URL, max_queue_size=max_queue_size)

    logger.debug("[EventBus] 使用 TaskEventBus（进程内模式）")
    return TaskEventBus(max_queue_size=max_queue_size)
