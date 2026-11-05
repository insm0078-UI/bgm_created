"""Entry point: ``python -m bgm_engine --port N`` (token via BGM_ENGINE_TOKEN env)."""

import argparse
import os
import sys

import uvicorn
from loguru import logger

from bgm_engine.history import HistoryStore
from bgm_engine.jobs import JobStore
from bgm_engine.pipeline import build_runner
from bgm_engine.runtime import EngineRuntime
from bgm_engine.server import create_app


def main() -> None:
    """Parse arguments, start model loading, and serve on 127.0.0.1."""
    parser = argparse.ArgumentParser(description="AI BGM Studio engine")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--project-root", default=os.environ.get("ACESTEP_PROJECT_ROOT", ""))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    token = os.environ.get("BGM_ENGINE_TOKEN")
    if not token or not args.project_root:
        logger.error("BGM_ENGINE_TOKEN and --project-root/ACESTEP_PROJECT_ROOT are required")
        sys.exit(2)

    os.environ["ACESTEP_PROJECT_ROOT"] = args.project_root
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.chdir(args.project_root)
    os.makedirs(args.output_dir, exist_ok=True)

    runtime = EngineRuntime(args.project_root, args.output_dir)
    history = HistoryStore(os.path.join(args.output_dir, "history.db"))
    store = JobStore(build_runner(runtime, history))
    runtime.load_async()
    app = create_app(runtime, store, token, history)
    logger.info(f"ENGINE_LISTENING port={args.port}")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
