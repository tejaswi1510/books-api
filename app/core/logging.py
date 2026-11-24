"""Console logging setup. All application logs go to the terminal (stdout)."""
import logging
import sys
import json

from app.core.request_id import request_id_ctx

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"


class RequestIDFilter(logging.Filter):
    """Attaches the current request id to every log record, so the format can print it.
    Outside a request (for example at startup) the id shows as '-'."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True

class JsonFormatter(logging.Formatter):
    """One JSON object per log line, easy for tools like CloudWatch to search."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIDFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())