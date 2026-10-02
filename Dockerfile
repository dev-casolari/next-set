FROM ghcr.io/astral-sh/uv:0.12.18 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv/nextset
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && useradd --system --uid 10001 --create-home nextset
COPY --chown=nextset:nextset app ./app
USER nextset
EXPOSE 8000
CMD ["/srv/nextset/.venv/bin/python", "-m", "app"]
