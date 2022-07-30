from abc import ABC, abstractmethod
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Callable
from unitunes import PlaylistManager
import time

GuiCallback = Callable[[], None]


class JobStatus(Enum):
    PENDING = 0
    RUNNING = 1
    SUCCESS = 2
    FAILED = 3
    CANCELLED = 4


class Job(ABC):
    type: str
    description: str
    playlist_name: str  # playlist the job operates on
    size: int = 0
    progress: int = 0
    gui_callback: GuiCallback
    status: JobStatus = JobStatus.PENDING

    @abstractmethod
    def execute(self):
        ...

    def is_done(self):
        completed_states = [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED]
        return self.status in completed_states


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
        self.status = JobStatus.SUCCESS


class PullJob(Job):
    type = "pull"
    pm: PlaylistManager

    def __init__(
        self, playlist_name: str, gui_callback: GuiCallback, pm: PlaylistManager
    ):
        self.playlist_name = playlist_name
        self.gui_callback = gui_callback
        self.pm = pm
        self.description = f"Pull {playlist_name}"

    def execute(self):
        def progress_callback(progress: int, size: int):
            self.progress = progress
            self.size = size
            assert self.progress <= self.size
            assert self.size > 0
            self.gui_callback()

        print(f"Pulling playlist {self.playlist_name}")
        self.status = JobStatus.RUNNING
        self.gui_callback()
        self.pm.pull_playlist(
            self.playlist_name,
            progress_callback=progress_callback,
        )
        self.status = JobStatus.SUCCESS
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
            job.status = JobStatus.RUNNING
            try:
                job.execute()
            except Exception as e:
                print(f"Job {job_id} failed: {e}")
                job.status = JobStatus.FAILED
            assert job.status != JobStatus.RUNNING
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
