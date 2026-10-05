# SPDX-FileCopyrightText: 2024 Osnabrück University of Applied Sciences
# SPDX-FileContributor: Andreas Schliebitz
# SPDX-FileContributor: Henri Graf
# SPDX-FileContributor: Jonas Tüpker
# SPDX-FileContributor: Lukas Hesse
# SPDX-FileContributor: Maik Fruhner
# SPDX-FileContributor: Prof. Dr.-Ing. Heiko Tapken
# SPDX-FileContributor: Tobias Wamhof
# SPDX-FileContributor: Philipp Schröer
#
# SPDX-License-Identifier: MIT

# MinIO no longer publishes container images (minio/minio is gone from Docker Hub and Quay), so the
# server is built from source at the same release tag the platform used before. The runtime mirrors
# the former official image: same binary path, entrypoint script, environment and volume.
ARG MINIO_IMAGE_TAG="RELEASE.2023-08-16T20-17-30Z"

FROM golang:1.21-bookworm AS build
ARG MINIO_IMAGE_TAG
RUN git clone --depth 1 --branch "${MINIO_IMAGE_TAG}" https://github.com/minio/minio.git /src
WORKDIR /src
# Version information as set by MinIO's own build (buildscripts/gen-ldflags.go)
RUN version="$(echo "${MINIO_IMAGE_TAG#RELEASE.}" | sed -E 's/T([0-9]{2})-([0-9]{2})-([0-9]{2})Z/T\1:\2:\3Z/')" \
    && commit="$(git rev-parse HEAD)" && short="$(git rev-parse --short=12 HEAD)" \
    && CGO_ENABLED=0 go build -trimpath -tags kqueue -o /out/minio \
       -ldflags "-s -w -X github.com/minio/minio/cmd.Version=${version} \
                 -X github.com/minio/minio/cmd.ReleaseTag=${MINIO_IMAGE_TAG} \
                 -X github.com/minio/minio/cmd.CommitID=${commit} \
                 -X github.com/minio/minio/cmd.ShortCommitID=${short} \
                 -X github.com/minio/minio/cmd.GOPATH=/go -X github.com/minio/minio/cmd.GOROOT=/usr/local/go" \
    && cp dockerscripts/docker-entrypoint.sh /out/docker-entrypoint.sh

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
ENV MINIO_ACCESS_KEY_FILE=access_key \
    MINIO_SECRET_KEY_FILE=secret_key \
    MINIO_ROOT_USER_FILE=access_key \
    MINIO_ROOT_PASSWORD_FILE=secret_key \
    MINIO_KMS_SECRET_KEY_FILE=kms_master_key \
    MINIO_CONFIG_ENV_FILE=config.env
COPY --from=build /out/minio /usr/bin/minio
COPY --from=build /out/docker-entrypoint.sh /usr/bin/docker-entrypoint.sh
RUN chmod +x /usr/bin/minio /usr/bin/docker-entrypoint.sh
EXPOSE 9000
VOLUME ["/data"]
COPY wait-for-keycloak.sh .
ENTRYPOINT [ "./wait-for-keycloak.sh", "/usr/bin/docker-entrypoint.sh" ]
CMD ["minio"]
