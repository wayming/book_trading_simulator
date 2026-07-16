"""Environment-based configuration for Book Trading Simulator."""

import os

DB_PATH = os.getenv("DB_PATH", "data/book_simulator.db")
ITICK_TOKEN = os.getenv("ITICK_TOKEN", "")
INITIAL_FUND = float(os.getenv("INITIAL_FUND", "10000.0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", "logs")
