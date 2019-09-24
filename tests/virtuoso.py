from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from queue import Queue, Empty
from select import select
from sys import executable
from os import fdopen
from pty import openpty

from skillbridge.server import python_server


class Virtuoso(Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.daemon = True

        self.queue = Queue()
        self.questions = []
        self.should_run = True
        self.server = None
        self.running = False
        self.pin = None

    def wait_until_ready(self):
        while not self.running:
            if not self.should_run:
                raise RuntimeError("could not start server")

    def _create_subprocess(self):
        script = python_server.__file__
        master, slave = openpty()
        self.server = Popen(
            [executable, script, 'testmode'],
            stdin=slave, stdout=PIPE, stderr=STDOUT,
            universal_newlines=True
        )

        self.pin = fdopen(master, 'w')

    def _wait_for_notification(self):
        read = self.read()
        assert read == 'running', f"expected 'running', got {read!r}"

    def run(self):
        try:
            self._run()
        finally:
            self.running = False
            self.should_run = False
            self.server.kill()
            self.server.wait()

    def _run(self):
        self._create_subprocess()
        self._wait_for_notification()

        while self.should_run:
            self.running = True

            question = self.read()
            if question is None:
                continue
            self.questions.append(question)

            try:
                answer = self.queue.get_nowait()
            except Empty:
                raise RuntimeError(f"no answer availyble for {question!r}")
            self.write(answer)

    def read(self):
        readable, _, _ = select([self.server.stdout], [], [], 1)
        if readable:
            return self.server.stdout.readline().strip()

    def write(self, message):
        self.pin.write(message + '\n')

    def stop(self):
        self.should_run = False
        self.join()
        self.server.kill()
        self.server.wait()

    def answer_with(self, status, message):
        self.queue.put(status + ' ' + message)

    def answer_success(self, message):
        self.answer_with('success', message)

    def answer_failure(self, message):
        self.answer_with('failure', message)

    @property
    def last_question(self):
        if self.questions:
            return self.questions.pop()
