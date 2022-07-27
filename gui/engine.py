from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Callable
from unitunes import PlaylistManager, FileManager, Index
import time

GuiCallback = Callable[[], None]


class Job(ABC):
    type: str
    description: str
    playlist_name: str  # playlist the job operates on
    service_names: list[str]  # services the job operates on
    size: int
    progress: int = 0
    gui_callback: GuiCallback

    @abstractmethod
    def execute(self):
        ...


class SleepJob(Job):
    type = "sleep"
    description = "Sleep"

    def __init__(self, duration: int, gui_callback: GuiCallback):
        self.duration = duration
        self.size = duration
        self.gui_callback = gui_callback

    def execute(self):
        print(f"Sleeping for {self.duration} seconds")
        for i in range(self.duration):
            time.sleep(1)
            self.progress += 1
            self.gui_callback()


class Engine:
    _pm: PlaylistManager
    _queue: Queue[int] = Queue()
    _jobs: dict[int, Job] = {}
    thread: Thread

    def __init__(self, pm: PlaylistManager) -> None:
        self._pm = pm
        self.thread = Thread(target=self._process_queue, daemon=True)
        self.thread.start()

    def _process_queue(self) -> None:
        while True:
            job_id = self._queue.get()
            job = self._jobs[job_id]
            print(f"Executing job {job_id}: {job.description}")
            job.execute()
            print(f"Finished job {job_id}: {job.description}")

    def _generate_id(self) -> int:
        """Generate a unique job id."""
        return len(self._jobs)  # assumes jobs are not removed from _jobs

    def push_job(self, job: Job) -> int:
        job_id = self._generate_id()
        self._jobs[job_id] = job
        self._queue.put(job_id)
        return job_id

    def get_job(self, job_id: int) -> Job:
        return self._jobs[job_id]
