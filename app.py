"""
Root entrypoint. Kept thin on purpose -- the real application lives in
src/api/app.py so it stays importable/testable as a package. This file
exists because Docker/gunicorn and most PaaS platforms (Render, Railway,
Heroku) expect `app.py` or `app:app` at the project root.
"""
from src.api.app import app  # noqa: F401

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
