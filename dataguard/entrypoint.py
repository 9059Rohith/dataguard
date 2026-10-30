"""Container bootstrap; ECS can inject separate password and host secrets safely."""

import os

from sqlalchemy.engine import URL

from dataguard.service import Pipeline


def main():
    port = os.getenv("PORT", "8000")
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = URL.create(
            "postgresql+psycopg",
            username=os.environ["DATABASE_USER"],
            password=os.environ["DATABASE_PASSWORD"],
            host=os.environ["DATABASE_HOST"],
            database=os.getenv("DATABASE_NAME", "dataguard"),
            query={"sslmode": os.getenv("DATABASE_SSLMODE", "require")},
        ).render_as_string(hide_password=False)
    pipeline = Pipeline(os.environ["DATABASE_URL"])
    pipeline.initialize()
    pipeline.engine.dispose()
    os.environ["DATAGUARD_AUTO_INIT"] = "false"
    # Container ingress is restricted by Compose loopback binding or platform security groups.
    os.execvp(
        "uvicorn",
        ["uvicorn", "dataguard.api:app", "--host", "0.0.0.0", "--no-access-log", "--port", port],
    )  # nosec B104


if __name__ == "__main__":
    main()
