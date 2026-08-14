FROM python:3.13-slim

WORKDIR /runner
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4"
COPY infra/migrations/runner.py /runner/runner.py
COPY spec/migrations /migrations

USER 65532:65532
ENTRYPOINT ["python", "/runner/runner.py"]
