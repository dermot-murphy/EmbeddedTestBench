# The Python legs of CI in one image, so they can be run before pushing (#282).
#
# tests.yml runs the suite on Python 3.8, 3.9 and 3.12, and lint.yml runs
# pylint on 3.12. The bench PC has none of 3.8, 3.9 or 3.12, which is how #281
# failed in CI after passing locally. This image holds one virtual environment
# per leg, each with the library versions in constraints/, which CI installs
# from too, so the image and CI cannot drift apart.
#
# Build, from the repository root:
#
#     docker build -f docker/ci/Dockerfile -t etb-ci .
#
# Run: see docker/ci/etb-ci, or the User Manual section 2.6.
#
# Where the Pythons come from:
#
# - 3.9 and 3.12 are python-build-standalone builds installed by uv, at the
#   patch versions actions/setup-python gave CI when this was written (3.9.25,
#   3.12.15). Change PYTHONS when CI's versions move.
# - 3.8 is the deadsnakes package: 3.8.20, where CI has 3.8.18. The standalone
#   3.8 links _tkinter into the interpreter, and matplotlib 3.7.5, the last
#   release for 3.8, cannot load its Tk backend from such a build, so a test
#   that CI passes failed here. deadsnakes builds _tkinter as a module, as the
#   runner's Python does. The patch version is the difference left.

# Pinned by digest: ubuntu:24.04, as the 3.9 and 3.12 legs use. CI runs 3.8 on
# 22.04 only because 3.8 is not in 24.04's tool cache.
FROM ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS pythons

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

# git reads the line ending of each file in the mounted checkout (etb-ci).
# python3.8-tk: see above.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git gnupg \
        software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get install -y --no-install-recommends python3.8 python3.8-venv python3.8-tk \
    && apt-get purge -y --auto-remove software-properties-common \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

ARG PYTHONS="3.9.25 3.12.15"
RUN for version in $PYTHONS; do \
        uv python install "$version" \
        && uv venv --quiet --python "$version" "/opt/venv/${version%.*}" || exit 1; \
    done \
    && uv venv --quiet --python 3.12 /opt/venv/lint \
    && uv venv --quiet --python /usr/bin/python3.8 /opt/venv/3.8

COPY docker/ci/etb-ci /usr/local/bin/etb-ci
# .gitattributes keeps the script LF; the sed covers a checkout made before it.
RUN sed -i 's/\r$//' /usr/local/bin/etb-ci && chmod 0755 /usr/local/bin/etb-ci
ENTRYPOINT ["etb-ci"]

# The legs, with their libraries. Built separately from the stage above so that
# "etb-ci lock" can run before constraints/ exists.
FROM pythons AS legs

COPY constraints/ /opt/constraints/
RUN uv pip install --quiet --python /opt/venv/3.8 -r /opt/constraints/py3.8.txt \
    && uv pip install --quiet --python /opt/venv/3.9 -r /opt/constraints/py3.9.txt \
    && uv pip install --quiet --python /opt/venv/3.12 -r /opt/constraints/py3.12.txt \
    && uv pip install --quiet --python /opt/venv/lint -r /opt/constraints/lint.txt
