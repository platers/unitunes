from enum import Enum
from queue import Queue
from threading import Thread
import traceback
from typing import Callable
from unitunes import PlaylistManager

GuiCallback = Callable[[], None]


class JobStatus(Enum):
    PENDING = 0
    RUNNING = 1
    SUCCESS = 2
    FAILED = 3
    CANCELLED = 4


class JobType(Enum):
    PULL = 0
    PUSH = 1
    SEARCH = 2


class Job:
    type: JobType
    description: str
    playlist_id: str  # playlist the job operates on
    size: int = 0
    progress: int = 0
    gui_callback: GuiCallback
    status: JobStatus = JobStatus.PENDING
    pm: PlaylistManager

    def __init__(
        self,
        type: JobType,
        playlist_name: str,
        gui_callback: GuiCallback,
        pm: PlaylistManager,
    ):
        self.playlist_id = playlist_name
        self.gui_callback = gui_callback
        self.pm = pm
        self.type = type

        if type == JobType.PULL:
            self.description = f"Pull {playlist_name}"
        elif type == JobType.PUSH:
            self.description = f"Push {playlist_name}"
        elif type == JobType.SEARCH:
            self.description = f"Search {playlist_name}"

    def execute(self):
        def progress_callback(progress: int, size: int):
            self.progress = progress
            self.size = size
            assert self.progress <= self.size
            self.gui_callback()

        self.status = JobStatus.RUNNING
        self.gui_callback()

        if self.type == JobType.PULL:
            self.pm.pull_playlist(
                self.playlist_id,
                progress_callback=progress_callback,
            )
        elif self.type == JobType.PUSH:
            self.pm.push_playlist(
                self.playlist_id,
                progress_callback=progress_callback,
            )
        elif self.type == JobType.SEARCH:
            self.pm.search_playlist(
                self.playlist_id,
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
                traceback.print_exc()
                job.status = JobStatus.FAILED

            assert job.status != JobStatus.RUNNING
            print(f"Finished job {job_id}: {job.description}")

            job.gui_callback()

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

    def jobs(self) -> list[Job]:
        return list(self._jobs.values())
