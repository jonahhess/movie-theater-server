import logging

from fastapi import FastAPI, Request

from tickets.src import redis_client
from tickets.src.error_handlers import register_exception_handlers
from tickets.src.router import protected_router, router as tickets_router

logger = logging.getLogger(__name__)

tickets = FastAPI(title="Tickets", lifespan=redis_client.lifespan)


@tickets.middleware("http")
async def log_requests(request: Request, call_next):
	logger.info("tickets request started: %s %s", request.method, request.url.path)
	try:
		response = await call_next(request)
	except Exception:
		logger.exception("tickets request failed: %s %s", request.method, request.url.path)
		raise

	logger.info(
		"tickets request finished: %s %s -> %s",
		request.method,
		request.url.path,
		response.status_code,
	)
	return response

register_exception_handlers(tickets)

tickets.include_router(tickets_router)
tickets.include_router(protected_router)
