"""Error tracking middleware — captures unhandled exceptions to error_events table."""
import logging
import traceback as tb

logger = logging.getLogger(__name__)


async def log_error_event(request, exc):
    """Log unhandled exceptions to the error_events table.

    This must never raise — any failure is silently swallowed so it cannot
    interfere with the normal error response path.
    """
    try:
        from saas.database import async_session_factory
        from saas.jobs.models import ErrorEvent

        if async_session_factory is None:
            return

        async with async_session_factory() as session:
            event = ErrorEvent(
                source="api",
                message=str(exc)[:4096],
                traceback=tb.format_exc()[:8192],
                request_path=str(request.url.path)[:500],
            )
            session.add(event)
            await session.commit()
    except Exception:
        logger.debug("Could not log error event", exc_info=True)
