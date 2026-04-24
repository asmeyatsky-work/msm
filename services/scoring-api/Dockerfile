# scoring-api — Rust hot path. Multi-stage for small final image.
FROM rust:1.89-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config libssl-dev protobuf-compiler \
 && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN cargo build --release --bin scoring-api

FROM gcr.io/distroless/cc-debian12:nonroot
WORKDIR /app
COPY --from=builder /build/target/release/scoring-api /app/scoring-api
USER nonroot
EXPOSE 8080
ENTRYPOINT ["/app/scoring-api"]
