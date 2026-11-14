# Prototype bench image: benchtools and an ARM GDB, with no instrument inside
# (#70). The recommendation and the measurements behind it are in
# docs/docker/Bench_Container_Investigation.md (ETB-DOCK-001).
#
# What is in it: Python 3.12 with benchtools[spec,serial] at the pins in
# constraints/py3.12.txt, and arm-none-eabi-gdb from the Arm GNU Toolchain
# release the bench PC uses (14.2.Rel1, GDB 15.2). What is not: the J-Link
# software, and every USB or serial device. The container reaches the J-Link
# GDB Server on the host over TCP (jlink://host.docker.internal:2331) and a
# serial instrument through a port the host publishes over TCP
# (serial://socket://host.docker.internal:<port>).
#
# A prototype: not built by CI, not published, and not yet used for a run on
# the real bench. ETB-DOCK-001 section 6 is the test plan for that.
#
# Build, from the repository root:
#
#     docker build -f docker/bench/Dockerfile -t etb-bench .
#
# Run (PowerShell), with the checkout mounted for specs/ and benches/:
#
#     docker run --rm -v "${PWD}:/work" -w /work etb-bench --version

# Pinned by digest: the same ubuntu:24.04 as docker/ci/Dockerfile.
FROM ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS gdb

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

# The release and its SHA-256 as Arm publishes them (the .sha256asc file
# beside the archive). Change both together.
ARG ARM_TOOLCHAIN=14.2.rel1
ARG ARM_TOOLCHAIN_SHA256=62a63b981fe391a9cbad7ef51b17e49aeaa3e7b0d029b36ca1e9c3b2a9b78823
RUN curl -fsSL -o /tmp/arm.tar.xz \
        "https://developer.arm.com/-/media/Files/downloads/gnu/${ARM_TOOLCHAIN}/binrel/arm-gnu-toolchain-${ARM_TOOLCHAIN}-x86_64-arm-none-eabi.tar.xz" \
    && echo "${ARM_TOOLCHAIN_SHA256}  /tmp/arm.tar.xz" | sha256sum -c - \
    && mkdir -p /tmp/arm /opt/arm/bin /opt/arm/share \
    && tar -xJf /tmp/arm.tar.xz -C /tmp/arm --strip-components=1 \
    && cp /tmp/arm/bin/arm-none-eabi-gdb /opt/arm/bin/ \
    && cp -r /tmp/arm/share/gdb /opt/arm/share/ \
    && cp /tmp/arm/*manifest.txt /opt/arm/ \
    && rm -rf /tmp/arm /tmp/arm.tar.xz

FROM ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

# arm-none-eabi-gdb's shared libraries outside glibc, from ldd on 2026-11-14:
# all four are in the base image already, and are named so that a change of
# base shows the need. ca-certificates: uv fetches Python over HTTPS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
        libncursesw6 libstdc++6 libzstd1 liblzma5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gdb /opt/arm /opt/arm
RUN ln -s /opt/arm/bin/arm-none-eabi-gdb /usr/local/bin/arm-none-eabi-gdb

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

# The patch version CI's 3.12 leg uses (docker/ci/Dockerfile).
ARG PYTHON=3.12.15
RUN uv python install "$PYTHON" && uv venv --quiet --python "$PYTHON" /opt/venv

# The package from the checkout, with CI's exact library versions.
COPY constraints/py3.12.txt /opt/constraints/py3.12.txt
COPY pyproject.toml README.md /opt/src/
COPY benchtools/ /opt/src/benchtools/
RUN uv pip install --quiet --python /opt/venv -c /opt/constraints/py3.12.txt \
        "/opt/src[spec,serial]" \
    && rm -rf /opt/src

# Identification, so a run can say which image produced it (ETB-DOCK-001 §5).
# REVISION is the commit the image was built from: pass --build-arg
# REVISION=$(git rev-parse HEAD). Nothing in benchtools reads these yet.
ARG REVISION=unknown
LABEL org.opencontainers.image.title="etb-bench" \
      org.opencontainers.image.description="Embedded Test Bench tools and ARM GDB, no instruments (prototype, #70)" \
      org.opencontainers.image.source="https://github.com/dermot-murphy/EmbeddedTestBench" \
      org.opencontainers.image.revision="$REVISION"
ENV ETB_IMAGE_REVISION=$REVISION

WORKDIR /work
ENTRYPOINT ["python", "-m", "benchtools"]
