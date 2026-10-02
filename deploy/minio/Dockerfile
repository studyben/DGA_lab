# Build the same upstream releases formerly pulled from Quay. No floating source.
FROM golang:1.24.2-bookworm AS server-build
WORKDIR /src
RUN git init . && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth 1 origin 0d7408fc9969caf07de6a8c3a84f9fbb10a6739e \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = 0d7408fc9969caf07de6a8c3a84f9fbb10a6739e
RUN CGO_ENABLED=0 go build -mod=readonly -tags kqueue -trimpath \
    -ldflags "$(go run buildscripts/gen-ldflags.go 2025-04-22T22:12:26Z)" -o /out/minio .

FROM golang:1.24.2-bookworm AS client-build
WORKDIR /src
RUN git init . && git remote add origin https://github.com/minio/mc.git \
    && git fetch --depth 1 origin b00526b153a31b36767991a4f5ce2cced435ee8e \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = b00526b153a31b36767991a4f5ce2cced435ee8e
RUN CGO_ENABLED=0 go build -mod=readonly -tags kqueue -trimpath \
    -ldflags "$(go run buildscripts/gen-ldflags.go 2025-04-16T18:13:26Z)" -o /out/mc .

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM runtime AS server
COPY --from=server-build /out/minio /usr/local/bin/minio
COPY --from=server-build /src/LICENSE /usr/share/licenses/minio/LICENSE
RUN minio --version
ENTRYPOINT ["minio"]
CMD ["server", "/data"]

FROM runtime AS client
COPY --from=client-build /out/mc /usr/local/bin/mc
COPY --from=client-build /src/LICENSE /usr/share/licenses/mc/LICENSE
RUN mc --version
ENTRYPOINT ["mc"]
