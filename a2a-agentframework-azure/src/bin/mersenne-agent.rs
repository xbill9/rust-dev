//! Native A2A v1.0 Mersenne prime agent built on the official Rust SDK
//! (`a2a-lf` + `a2a-server-lf` from github.com/a2aproject/a2a-rs).
//!
//! Serves JSON-RPC at `/jsonrpc`, HTTP+JSON (REST) at `/rest` and the agent
//! card at `/.well-known/agent-card.json`.
//!
//! Env: `PORT` (default 8304), `HOST` (default 0.0.0.0),
//!      `ADVERTISE_URL` (default http://localhost:$PORT).

use std::sync::Arc;

use a2a::event::StreamResponse;
use a2a::*;
use a2a_benchmark_rust::{DEFAULT_COUNT, find_mersenne_primes, parse_count};
use a2a_server::*;
use futures::stream::{self, BoxStream, StreamExt};

struct MersenneExecutor;

/// Count from the request: a data part `{"count": n}` wins, else the first
/// positive number in any text part, else the default.
fn requested_count(message: Option<&Message>) -> usize {
    let Some(msg) = message else {
        return DEFAULT_COUNT;
    };
    for part in &msg.parts {
        // Data parts travel as protobuf `Struct`, so `{"count": 6}` can
        // arrive as 6.0: accept any whole positive number.
        if let PartContent::Data(v) = &part.content
            && let Some(n) = v.get("count").and_then(|n| n.as_f64())
            && n >= 1.0
            && n.fract() == 0.0
        {
            return n as usize;
        }
    }
    msg.parts
        .iter()
        .filter_map(|p| p.as_text())
        .find_map(parse_count)
        .unwrap_or(DEFAULT_COUNT)
}

fn status(state: TaskState, message: Option<Message>) -> TaskStatus {
    TaskStatus {
        state,
        message,
        timestamp: Some(chrono::Utc::now()),
    }
}

impl AgentExecutor for MersenneExecutor {
    fn execute(
        &self,
        ctx: ExecutorContext,
    ) -> BoxStream<'static, Result<StreamResponse, A2AError>> {
        let count = requested_count(ctx.message.as_ref());
        let task_id = ctx.task_id.clone();
        let context_id = ctx.context_id.clone();

        let working = StreamResponse::StatusUpdate(TaskStatusUpdateEvent {
            task_id: task_id.clone(),
            context_id: context_id.clone(),
            status: status(TaskState::Working, None),
            metadata: None,
        });

        let done = async move {
            // Big-integer work is CPU-bound; keep it off the async workers.
            let report = tokio::task::spawn_blocking(move || find_mersenne_primes(count))
                .await
                .map_err(|e| A2AError::internal(format!("worker panicked: {e}")))?;
            tracing::info!(
                requested = report.requested,
                found = report.found,
                elapsed_ms = report.elapsed_ms,
                "computed"
            );
            let summary = report.summary();
            let data = serde_json::to_value(&report)
                .map_err(|e| A2AError::internal(format!("serialise report: {e}")))?;

            Ok(StreamResponse::Task(Task {
                id: task_id.clone(),
                context_id: context_id.clone(),
                status: status(
                    TaskState::Completed,
                    Some(Message {
                        role: Role::Agent,
                        message_id: new_message_id(),
                        task_id: Some(task_id),
                        context_id: Some(context_id),
                        parts: vec![Part::text(summary.clone())],
                        metadata: None,
                        extensions: None,
                        reference_task_ids: None,
                    }),
                ),
                artifacts: Some(vec![Artifact {
                    artifact_id: new_artifact_id(),
                    name: Some("mersenne-report".into()),
                    description: Some("Structured timing for the Lucas-Lehmer run".into()),
                    parts: vec![Part::text(summary), Part::data(data)],
                    metadata: None,
                    extensions: None,
                }]),
                history: None,
                metadata: None,
            }))
        };

        Box::pin(stream::once(async { Ok(working) }).chain(stream::once(done)))
    }

    fn cancel(&self, ctx: ExecutorContext) -> BoxStream<'static, Result<StreamResponse, A2AError>> {
        let event = StreamResponse::StatusUpdate(TaskStatusUpdateEvent {
            task_id: ctx.task_id.clone(),
            context_id: ctx.context_id.clone(),
            status: status(TaskState::Canceled, None),
            metadata: None,
        });
        Box::pin(stream::once(async { Ok(event) }))
    }
}

fn agent_card(base: &str) -> AgentCard {
    AgentCard {
        name: "Mersenne Prime Agent Rust".into(),
        description: "A Rust A2A v1.0 agent (official a2a-rs SDK) that confirms the first n \
                      Mersenne primes with the Lucas-Lehmer test and reports the elapsed time."
            .into(),
        version: env!("CARGO_PKG_VERSION").into(),
        provider: None,
        capabilities: AgentCapabilities {
            streaming: Some(true),
            push_notifications: Some(false),
            extensions: None,
            extended_agent_card: None,
        },
        skills: vec![AgentSkill {
            id: "find-mersenne-rust".into(),
            name: "Find Mersenne Primes in Rust".into(),
            description: "Finds the first n Mersenne primes (n <= 26) and times the run.".into(),
            tags: vec!["math".into(), "benchmark".into()],
            examples: Some(vec!["Calculate the first 20 Mersenne primes".into()]),
            input_modes: None,
            output_modes: None,
            security_requirements: None,
        }],
        default_input_modes: vec!["text/plain".into(), "application/json".into()],
        default_output_modes: vec!["text/plain".into(), "application/json".into()],
        supported_interfaces: vec![
            AgentInterface::new(format!("{base}/jsonrpc"), TRANSPORT_PROTOCOL_JSONRPC),
            AgentInterface::new(format!("{base}/rest"), TRANSPORT_PROTOCOL_HTTP_JSON),
        ],
        security_schemes: None,
        security_requirements: None,
        documentation_url: None,
        icon_url: None,
        signatures: None,
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .init();

    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8304);
    let host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".into());
    let base =
        std::env::var("ADVERTISE_URL").unwrap_or_else(|_| format!("http://localhost:{port}"));
    let base = base.trim_end_matches('/').to_string();

    let handler = Arc::new(DefaultRequestHandler::new(
        MersenneExecutor,
        InMemoryTaskStore::new(),
    ));
    let card = Arc::new(StaticAgentCard::new(agent_card(&base)));

    let app = axum::Router::new()
        .nest(
            "/jsonrpc",
            a2a_server::jsonrpc::jsonrpc_router(handler.clone()),
        )
        .nest("/rest", a2a_server::rest::rest_router(handler))
        .merge(a2a_server::agent_card::agent_card_router(card));

    let addr = format!("{host}:{port}");
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .unwrap_or_else(|e| panic!("bind {addr}: {e}"));
    tracing::info!("Mersenne Prime Agent Rust listening on {addr}");
    tracing::info!("Agent card: {base}/.well-known/agent-card.json");
    tracing::info!("JSON-RPC:   {base}/jsonrpc");
    tracing::info!("REST:       {base}/rest");
    axum::serve(listener, app).await.expect("server error");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn count_from_text_and_data() {
        let m = Message::new(Role::User, vec![Part::text("first 9 please")]);
        assert_eq!(requested_count(Some(&m)), 9);
        let m = Message::new(
            Role::User,
            vec![
                Part::text("first 9"),
                Part::data(serde_json::json!({"count": 3})),
            ],
        );
        assert_eq!(requested_count(Some(&m)), 3);
        let m = Message::new(
            Role::User,
            vec![Part::data(serde_json::json!({"count": 6.0}))],
        );
        assert_eq!(requested_count(Some(&m)), 6);
        assert_eq!(requested_count(None), DEFAULT_COUNT);
    }
}
