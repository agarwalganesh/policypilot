"""
PolicyPilot — Application Entry Point
"""
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Ensure project root is in sys.path
sys.path.insert(0, str(PROJECT_ROOT))

# Vercel's deployment filesystem is read-only; only /tmp is writable.
# Copy the bundled ChromaDB index and SQLite DB there so they can be opened.
# Writes made on Vercel are lost when the instance is recycled.
if os.getenv("VERCEL"):
    tmp_root = Path("/tmp/policypilot")
    tmp_chroma = tmp_root / "chroma_db"
    tmp_db = tmp_root / "policypilot.db"
    if not tmp_chroma.exists() and (PROJECT_ROOT / "chroma_db").exists():
        shutil.copytree(PROJECT_ROOT / "chroma_db", tmp_chroma)
    if not tmp_db.exists() and (PROJECT_ROOT / "policypilot.db").exists():
        tmp_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / "policypilot.db", tmp_db)
    os.environ.setdefault("CHROMA_PERSIST_DIR", str(tmp_chroma))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{tmp_db}")
    os.environ.setdefault("EMBEDDING_PROVIDER", "huggingface")

# Ensure UTF-8 output on Windows to handle Unicode from policy documents
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from backend.app import create_app
from backend.config import get_settings

settings = get_settings()
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=(settings.flask_env == "development"),
        use_reloader=False,
    )
