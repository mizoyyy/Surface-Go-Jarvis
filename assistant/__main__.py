"""python -m assistant: runs the assistant and the UI server."""

import logging

import uvicorn

from . import config


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("assistant.server:app", host=config.UI_HOST, port=config.UI_PORT,
                log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
