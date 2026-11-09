# Single-container environment for the sudoku-codec-frontier task.
#
# Nothing listens on a port and nothing is fetched at run time: the task is a
# pure computation over a corpus baked into the image, so it runs under
# Harbor's strictest policy, network_mode = "no-network".
FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl ca-certificates xz-utils git procps \
 && rm -rf /var/lib/apt/lists/*

# ── Agent harness, baked in ─────────────────────────────────────────────────
# The task runs with no network, so Claude Code cannot bootstrap itself at run
# time: its installer would apt-get nodejs and npm, and fail. Harbor skips that
# step entirely when `claude` is already on PATH, so it is installed here while
# the build still has network. That also pins the harness into the image rather
# than fetching a different version on every run.
ARG NODE_VERSION=22.23.4
ARG CLAUDE_CODE_VERSION=2.1.317
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) node_arch='x64' ;; \
      arm64) node_arch='arm64' ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" \
      -o /tmp/node.tar.xz; \
    mkdir -p /opt/node; \
    tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1; \
    rm /tmp/node.tar.xz; \
    ln -sf /opt/node/bin/node /usr/local/bin/node; \
    ln -sf /opt/node/bin/npm /usr/local/bin/npm; \
    ln -sf /opt/node/bin/npx /usr/local/bin/npx; \
    node --version; \
    npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"; \
    ln -sf /opt/node/bin/claude /usr/local/bin/claude; \
    claude --version

# ── Task content ────────────────────────────────────────────────────────────
# data/      the 39,151-puzzle training corpus and its provenance
# reference/ the article's codec, the shared gate logic, and the practice harness
# submission/ where the deliverable goes; pre-filled with the article's codec so
#            the harness runs green from the first command
COPY data /app/data
COPY reference /app/reference
COPY submission /app/submission
RUN chmod 0777 /app/submission

WORKDIR /app
CMD ["sleep", "infinity"]
