"""Step 8: optional Sentry tracing. With SENTRY_DSN unset, everything here is a no-op."""
import atexit
import contextlib
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_sentry = None  # the sentry_sdk module once initialised


def init() -> bool:
    """Initialise Sentry if SENTRY_DSN is set. Returns True when tracing is active."""
    global _sentry
    if _sentry is not None:
        return True
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=dsn, traces_sample_rate=1.0)
        _sentry = sentry_sdk
        atexit.register(lambda: sentry_sdk.flush(timeout=10))
        print("[INFO] Sentry tracing enabled")
        return True
    except BaseException as e:  # noqa: BLE001
        print(f"[WARN] Sentry init failed, continuing without tracing: {e}")
        return False


@contextlib.contextmanager
def span(name: str):
    """Time a block. No-op unless Sentry is active."""
    if _sentry is None:
        yield None
        return
    start = time.perf_counter()
    cm = None
    sp = None
    try:
        cm = _sentry.start_span(op=name, name=name)
        sp = cm.__enter__()
    except BaseException as e:  # noqa: BLE001
        print(f"[WARN] could not start Sentry span {name}: {e}")
        cm = None
    try:
        yield sp
    finally:
        dur = time.perf_counter() - start
        if sp is not None:
            try:
                sp.set_data("duration_s", round(dur, 3))
            except BaseException:  # noqa: BLE001
                pass
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except BaseException:  # noqa: BLE001
                pass
        print(f"[trace] {name} took {dur:.2f}s")
