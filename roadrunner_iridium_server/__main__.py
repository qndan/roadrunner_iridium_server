import sys
import argparse
import asyncio
import logging

from . import server

PROGRAM_NAME = "roadrunner-iridum-server"
DEFAULT_PORT = 47137
DEFAULT_HOSTNAME = "localhost"

logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(prog=PROGRAM_NAME,
                                 description="Run a WebSocket server to use roadrunnner in WebIridium")
parser.add_argument("-p", "--port",
                    type=int, default=DEFAULT_PORT,
                    help="Port to serve on")
parser.add_argument("--host",
                    type=str, default=DEFAULT_HOSTNAME,
                    help="Host to serve on")

def main():
    result = parser.parse_args()
    asyncio.run(server.start(result.host, result.port))

if __name__ == "__main__":
    main()
