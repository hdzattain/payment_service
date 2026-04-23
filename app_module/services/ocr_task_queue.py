import asyncio
from datetime import datetime, UTC
from contextlib import suppress
from typing import Awaitable, Callable

from app_module.core.config import settings
from app_module.logger.logger_config import setup_logger
from app_module.services.ocr_task_service import process_ocr_task_async

logger = setup_logger("ocr_task_queue")

TaskPayload = dict[str, object]
TaskProcessor = Callable[[str, str, bool], Awaitable[None]]


class OCRTaskQueueManager:
    """仅基于进程内通知队列的OCR任务管理器。"""

    def __init__(
        self,
        *,
        worker_count: int | None = None,
        queue_maxsize: int | None = None,
        task_processor: TaskProcessor | None = None,
    ) -> None:
        self.worker_count = max(1, worker_count or settings.OCR_TASK_CONSUMERS)
        self.queue_maxsize = max(1, queue_maxsize or settings.OCR_TASK_QUEUE_MAXSIZE)
        self.task_processor = task_processor or process_ocr_task_async

        self._worker_tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._running_task_ids: set[str] = set()
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[TaskPayload] = asyncio.Queue(maxsize=self.queue_maxsize)
        self._submitted_notifications = 0
        self._rejected_notifications = 0
        self._claimed_total = 0
        self._last_claimed_task_id: str | None = None
        self._last_claimed_at: str | None = None

    async def start(self) -> None:
        logger.info(
            "启动OCR任务队列 | workers=%s | queue_maxsize=%s",
            self.worker_count,
            self.queue_maxsize,
        )

        self._stop_event.clear()
        for worker_index in range(self.worker_count):
            worker = asyncio.create_task(self._worker_loop(worker_index), name=f"ocr-task-worker-{worker_index}")
            self._worker_tasks.append(worker)

    async def stop(self) -> None:
        logger.info("停止OCR任务队列")
        self._stop_event.set()

        for worker in self._worker_tasks:
            worker.cancel()

        if self._worker_tasks:
            results = await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    logger.error("OCR任务worker退出异常: %s", result, exc_info=True)
        self._worker_tasks.clear()

    async def submit_task(self, payload: TaskPayload) -> bool:
        """将新任务放入进程内队列，队列满时直接拒绝。"""
        task_id = str(payload.get("task_id", ""))
        async with self._lock:
            if self._queue.full():
                self._rejected_notifications += 1
                logger.warning("OCR任务通知队列已满，拒绝入队: task_id=%s", task_id or "unknown")
                return False

            self._queue.put_nowait(dict(payload))
            self._submitted_notifications += 1

        logger.info("收到新OCR任务通知并已入队: task_id=%s", task_id or "unknown")
        return True

    def get_runtime_stats(self) -> dict[str, object]:
        return {
            "worker_count": self.worker_count,
            "queue_maxsize": self.queue_maxsize,
            "queued_task_count": self._queue.qsize(),
            "running_task_count": len(self._running_task_ids),
            "running_task_ids": sorted(self._running_task_ids),
            "submitted_notifications": self._submitted_notifications,
            "rejected_notifications": self._rejected_notifications,
            "claimed_total": self._claimed_total,
            "last_claimed_task_id": self._last_claimed_task_id,
            "last_claimed_at": self._last_claimed_at,
        }

    async def _worker_loop(self, worker_index: int) -> None:
        logger.info("OCR任务worker已启动: worker=%s", worker_index)
        try:
            while not self._stop_event.is_set():
                payload = await self._queue.get()

                task_id = str(payload["task_id"])

                async with self._lock:
                    self._running_task_ids.add(task_id)
                    self._claimed_total += 1
                    self._last_claimed_task_id = task_id
                    self._last_claimed_at = datetime.now(UTC).isoformat()

                try:
                    logger.info("OCR任务开始消费: worker=%s, task_id=%s", worker_index, task_id)
                    await self.task_processor(
                        task_id,
                        str(payload["file_url"]),
                        bool(payload.get("merge_mode", False)),
                    )
                except Exception as exc:
                    logger.error("OCR任务消费失败: worker=%s, task_id=%s, error=%s", worker_index, task_id, exc, exc_info=True)
                finally:
                    async with self._lock:
                        self._running_task_ids.discard(task_id)
                    self._queue.task_done()
        except asyncio.CancelledError:
            logger.info("OCR任务worker已取消: worker=%s", worker_index)
            raise





