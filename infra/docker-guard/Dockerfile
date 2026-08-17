FROM python:3.13-slim

WORKDIR /app

COPY infra/docker-guard/proxy.py /app/proxy.py

# Run as non-root user (nobody:nobody / 65534:65534)
USER 65534:65534

EXPOSE 2375

CMD ["python", "-u", "/app/proxy.py"]
