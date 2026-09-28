FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && \
    groupadd --gid 10001 bot && useradd --uid 10001 --gid 10001 --no-create-home bot && \
    mkdir /bot-data && chown 10001:10001 /bot-data

FROM base AS bot
USER 10001:10001
CMD ["amnezia-bot"]

FROM docker:29-cli@sha256:018edbc908e08fcc9dbf029c812c34251e9b4719e6f71ca0e5eae2a987d014ca AS docker-cli

FROM base AS manager
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
USER 0:0
CMD ["amnezia-manager"]
