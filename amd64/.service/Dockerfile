# linux/amd64 variant. nodo builds it with --opt platform=linux/amd64 (from
# service.json). The debian:bookworm-slim digest below is a multi-arch index
# (linux/amd64 + linux/arm64/v8), so the same pin resolves to the linux/amd64
# image. Nothing is compiled during the build.

# Content-addressed: two packs of the same tree must produce the same image.
FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

# python3 is the runtime. No pip, no protobuf library: the decoder in
# service/config.py reads the few fields we need off the wire.
RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 \
    && rm -rf /var/lib/apt/lists/*

# The packer build context is .service/. Project files land under
# .service/service/. A source that starts with "./" is rewritten to that
# tree (COPY ./service -> COPY service/service). A source without the dot
# is not rewritten and the build fails.
COPY ./service /service
RUN chmod +x /service/entrypoint.py
