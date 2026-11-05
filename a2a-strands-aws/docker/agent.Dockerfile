# Rust A2A v1.0 agent for Lightsail (linux/amd64). Build context: rig root.
FROM rust:1.99.1-slim-trixie AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src src
RUN cargo build --release --locked --bin mersenne-agent

FROM debian:trixie-slim
COPY --from=build /src/target/release/mersenne-agent /usr/local/bin/mersenne-agent
ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080
CMD ["mersenne-agent"]
