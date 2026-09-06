FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ARG LITELLM_VERSION=1.92.0

RUN python -m pip install --no-cache-dir "litellm[proxy]==${LITELLM_VERSION}"
