"""Development entry point.

Run the API with::

    python main.py

or, equivalently::

    uvicorn app.main:app --reload
"""

import uvicorn

from app.main import app  # noqa: F401  (re-exported for ``uvicorn main:app``)

HOST = "0.0.0.0"
PORT = 8000


def main() -> None:
    """Start the development server with auto-reload."""
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
