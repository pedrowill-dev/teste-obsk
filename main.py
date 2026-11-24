"""Entrypoint of the robot: `python main.py` (the orchestrator runs it with the environment's settings)."""
from etl.pipeline import main

if __name__ == "__main__":
    main()
