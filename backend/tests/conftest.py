import os
import sys
from pathlib import Path

# Point at dummy connection strings so importing app.main / app.database
# never needs a real Postgres/Redis to be reachable — both libraries only
# parse the URL at import/construction time, they don't connect eagerly.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("UPLOAD_DIR", str(Path(__file__).resolve().parent / "_uploads"))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
