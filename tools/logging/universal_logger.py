# tools/logging/universal_logger.py

import json
import logging
import os
import inspect
from pathlib import Path
from datetime import datetime
import uuid

_LOGGER = None
_RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def _json_default(obj):
    try:
        return str(obj)
    except Exception:
        return "<non-serializable>"


def setup_universal_logger(log_dir=None, log_filename="benchmark_audit.log"):
    global _LOGGER

    if _LOGGER is not None:
        return _LOGGER

    if log_dir is None:
        project_root = Path(__file__).resolve().parents[2]
        log_dir = project_root / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename

    logger = logging.getLogger("tesis_universal_logger")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _LOGGER = logger
    return _LOGGER


def get_run_id():
    return _RUN_ID


def _build_log_line(level, solver, message, extra=None):
    frame = inspect.currentframe()
    caller = frame.f_back.f_back

    script = os.path.basename(caller.f_code.co_filename)
    function = caller.f_code.co_name
    line = caller.f_lineno
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    extra_str = ""
    if extra is not None:
        extra_str = json.dumps(extra, ensure_ascii=False, default=_json_default)

    return (
        f"{timestamp} | {level.upper():<7} | run_id={_RUN_ID} | "
        f"solver={solver} | script={script} | func={function} | line={line} | "
        f"msg={message}"
        + (f" | extra={extra_str}" if extra_str else "")
    )


def log_event(level, solver, message, extra=None):
    logger = setup_universal_logger()
    line = _build_log_line(level, solver, message, extra=extra)

    level = level.upper()
    if level == "DEBUG":
        logger.debug(line)
    elif level == "WARNING":
        logger.warning(line)
    elif level == "ERROR":
        logger.error(line)
    else:
        logger.info(line)


def log_exception(solver, message, exc, extra=None):
    payload = {} if extra is None else dict(extra)
    payload["exception_type"] = type(exc).__name__
    payload["exception_message"] = str(exc)
    log_event("ERROR", solver, message, extra=payload)