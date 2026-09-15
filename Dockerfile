FROM python:3.11-slim-bookworm AS build

WORKDIR /opt/CTFd

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        git \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY . /opt/CTFd

# Vendor PyYAML and openpgp.js/confetti/lolight into the plugin (gitignored,
# normally a host-side `tools/build_vendor.sh` step for the bind-mounted dev
# setup) so the image is self-contained for deployments, like k8s, that run
# from the image alone with no plugin bind mount.
RUN bash workshop_platform/tools/build_vendor.sh \
    && rm -rf CTFd/plugins/workshop \
    && cp -r workshop_platform/plugins/workshop CTFd/plugins/workshop

RUN pip install --no-cache-dir -r requirements.txt \
    && for d in CTFd/plugins/*; do \
        if [ -f "$d/requirements.txt" ]; then \
            pip install --no-cache-dir -r "$d/requirements.txt";\
        fi; \
    done;


FROM python:3.11-slim-bookworm AS release
WORKDIR /opt/CTFd

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libffi8 \
        libssl3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=1001:1001 --from=build /opt/CTFd /opt/CTFd

RUN useradd \
    --no-log-init \
    --shell /bin/bash \
    -u 1001 \
    ctfd \
    && mkdir -p /var/log/CTFd /var/uploads \
    && chown -R 1001:1001 /var/log/CTFd /var/uploads /opt/CTFd \
    && chmod +x /opt/CTFd/docker-entrypoint.sh \
    # The workshop plugin's default WORKSHOP_TOOLS path, so a bare `docker run`
    # of this image finds the tools without any env var. A dev bind mount at
    # the same path (docker-compose.yml) overlays this symlink transparently.
    && mkdir -p /opt/workshop \
    && ln -s /opt/CTFd/workshop_platform/tools /opt/workshop/tools

COPY --chown=1001:1001 --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

USER 1001
EXPOSE 8000
ENTRYPOINT ["/opt/CTFd/docker-entrypoint.sh"]
