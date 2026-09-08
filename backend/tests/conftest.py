from __future__ import annotations

import os
import tempfile
from pathlib import Path


test_data_dir = Path(tempfile.mkdtemp(prefix="debris-backend-test-"))
os.environ["DATA_DIR"] = str(test_data_dir)
os.environ["DATABASE_URL"] = f"sqlite:///{test_data_dir / 'test.db'}"
os.environ["QUEUE_MODE"] = "local"
