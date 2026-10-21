# Star Trader progress server. Pure Python standard library: no packages to install.
FROM python:3.12.7-slim-bookworm
WORKDIR /app
COPY save_server.py star_trader.py presence.py startup.py save_sync.py ./
RUN useradd --system --uid 10001 --home-dir /data startrader && mkdir -p /data && chown startrader /data
USER startrader
ENV STAR_TRADER_DB=/data/progress.sqlite3 \
    STAR_TRADER_SIGNUP=off \
    STAR_TRADER_NO_UPDATE_CHECK=1 \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=4)"
# Plain HTTP inside the container; the Caddy service in docker-compose.yml adds HTTPS.
CMD ["python", "save_server.py", "serve", "--host", "0.0.0.0", "--port", "8766", "--lan"]
