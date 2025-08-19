import json
import logging
import asyncio
import concurrent.futures
import threading

from websockets.asyncio.server import serve, ServerConnection
from pydantic import ValidationError

from .simulator import Simulator
from .actions import Action, TimeCourseAction, LoadModelAction
from .results import Result, TimeCourseResult, LoadModelResult

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
        def handle_message(message: str) -> Result:
            # TODO: how are errors handled?
            logger.debug("Message received: %s", message)

            try:
                action = Action.model_validate_json(message).root
            except ValidationError:
                logger.exception("Invalid message: %s", message)
                return

            simulator = local.simulator

            try:
                simulator.load_code(action.code)
            except ValueError as e:
                logger.exception("Conversion error: %s", e.args)
                return

            if action.code:
                simulator.load_code(action.code)

            match action:
                case LoadModelAction():
                    model_info = simulator.get_model_info()
                    return LoadModelResult(
                        id=action.id,
                        type="loadModel",
                        floating_species=model_info.floating_species,
                        boundary_species=model_info.boundary_species,
                        reactions=model_info.reactions,
                        parameters=model_info.parameters,
                    )
                case TimeCourseAction():
                    result = simulator.simulate_time_course(
                        action.start_time,
                        action.end_time,
                        action.number_of_points,
                        action.reset_initial_conditions,
                        action.selection_list,
                        action.variable_values,
                        action.parameter_scan_options,
                    )
                    return TimeCourseResult(
                        id=action.id,
                        type="timeCourse",
                        column_names=result.column_names,
                        rows=result.rows,
                    )
        
        async def dispatch_message(message: str):
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(executor, handle_message, message)

            if response:
                await connection.send(response.model_dump_json(by_alias=True))
            else:
                # TODO: send them an error
                pass

        async for message in connection:
            asyncio.create_task(dispatch_message(message))

