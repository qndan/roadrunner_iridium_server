import json
import logging
import asyncio
import concurrent.futures
import threading

from websockets.asyncio.server import serve, ServerConnection
from pydantic import ValidationError

from .simulator import Simulator
from .actions import Action, BareAction, TimeCourseAction, SteadyStateAction, LoadModelAction
from .results import Result, ErrorResult

MAX_THREADS_PER_SESSION = 4

logger: logging.Logger = logging.getLogger(__name__)

async def start(host: str, port: int) -> None:
    logger.info("Starting server on %s:%d", host, port)

    async with serve(handle, host, port) as server:
        await server.serve_forever()

local = threading.local()
def thread_initializer():
    local.simulator = Simulator()

async def handle(connection: ServerConnection):
    logger.info("Connection established: %s", connection)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_THREADS_PER_SESSION,
        initializer=thread_initializer,
    ) as executor:
        def handle_message(message: str) -> Result | None:
            # TODO: how are errors handled?
            logger.debug("Message received: %s", message)

            action = Action.model_validate_json(message).root
            simulator = local.simulator

            if action.code:
                simulator.load_code(action.code)

            match action:
                case LoadModelAction():
                    model_info = simulator.get_model_info()
                    return Result(
                        id=action.id,
                        data=simulator.get_model_info(),
                    )
                case TimeCourseAction():
                    payload = action.payload
                    return Result(
                        id=action.id,
                        data=simulator.simulate_time_course(
                            payload.start_time,
                            payload.end_time,
                            payload.number_of_points,
                            payload.reset_initial_conditions,
                            payload.selection_list,
                            payload.variable_values,
                            payload.parameter_scan_options,
                        ),
                    )
                case SteadyStateAction():
                    payload = action.payload
                    return Result(
                        id=action.id,
                        data=simulator.compute_steady_state(
                            variable_values=payload.variable_values,
                            parameter_scan_options=payload.parameter_scan_options,
                        ),
                    )
        
        async def dispatch_message(message: str):
            loop = asyncio.get_event_loop()
            response = None
            err = None
            try:
                response = await loop.run_in_executor(executor, handle_message, message)
            except Exception as e:
                logger.exception("Message handle error: %s", e.args)
                err = e

            if response:
                await connection.send(response.model_dump_json(by_alias=True))
            else:
                try:
                    bare_action = BareAction.model_validate_json(message)
                    error_result = ErrorResult(
                        id=bare_action.id,
                        error_message=str(err.args) if err else "Unexpected error occurred."
                    )
                    await connection.send(error_result.model_dump_json(by_alias=True))
                # TODO: send them an error
                except:
                    raise

        async for message in connection:
            asyncio.create_task(dispatch_message(message))

