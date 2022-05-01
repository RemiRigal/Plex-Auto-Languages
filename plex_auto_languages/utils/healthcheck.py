import json
import logging
from flask import Flask
from typing import Callable
from threading import Thread
from werkzeug.serving import make_server


flask_logger = logging.getLogger("werkzeug")
flask_logger.setLevel(logging.ERROR)


class HealthcheckServer(Thread):

    def __init__(self, name: str, is_ready: Callable, is_healthy: Callable):
        super().__init__()
        self._is_healthy = is_healthy
        self._is_ready = is_ready
        self._app = Flask(name)
        self._server = make_server("0.0.0.0", 9880, self._app)
        self._ctx = self._app.app_context()
        self._ctx.push()

        @self._app.route("/")
        @self._app.route("/health")
        def __health():
            healthy = self._is_healthy()
            code = 200 if healthy else 400
            return json.dumps({"healthy": healthy}), code

        @self._app.route("/ready")
        def __ready():
            ready = self._is_ready()
            code = 200 if ready else 400
            return json.dumps({"ready": ready}), code

    def run(self):
        self._server.serve_forever()

    def shutdown(self):
        self._server.shutdown()
