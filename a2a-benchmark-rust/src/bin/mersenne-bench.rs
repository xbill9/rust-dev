//! Benchmark client (official `a2a-client-lf`). Sends "Calculate the first N
//! Mersenne primes" to each agent for N in MIN..=MAX, REPS times each, and
//! records two numbers per call:
//!
//! * `compute_ms` — the agent's own Lucas-Lehmer time, read from the JSON
//!   report (data part for the native agent, JSON text line for exec mode);
//! * `rtt_ms`     — wall-clock round trip of `send_message` seen by this client.
//!
//! All statistics (median, min, max) are computed here, never by hand.
//!
//! Usage: mersenne-bench [--min 1] [--max 22] [--reps 5] [--out results.json]
//!                       [--agent name=url ...]
//! Default agents: native=http://localhost:8104  exec=http://localhost:8105

use std::time::Instant;

use a2a::*;
use a2a_benchmark_rust::Report;
use a2a_client::A2AClientFactory;
use a2a_client::agent_card::AgentCardResolver;
use serde::Serialize;
use serde_json::Value;

#[derive(Serialize)]
struct Row {
    agent: String,
    n: usize,
    found: usize,
    reps: usize,
    compute_ms_median: f64,
    compute_ms_min: f64,
    compute_ms_max: f64,
    rtt_ms_median: f64,
    rtt_ms_min: f64,
    rtt_ms_max: f64,
    overhead_ms_median: f64,
}

fn median(v: &mut [f64]) -> f64 {
    v.sort_by(|a, b| a.total_cmp(b));
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        (v[n / 2 - 1] + v[n / 2]) / 2.0
    }
}

/// Read a report object field by field. Data parts travel as protobuf
/// `Struct`, where every number is a double (`"found": 20.0`), so integers
/// are read as f64 and converted.
fn report_from_object(v: &Value) -> Option<Report> {
    let num = |k: &str| v.get(k).and_then(Value::as_f64);
    Some(Report {
        requested: num("requested")? as usize,
        found: num("found")? as usize,
        elapsed_ms: num("elapsed_ms")?,
        exponents: v
            .get("exponents")?
            .as_array()?
            .iter()
            .filter_map(Value::as_f64)
            .map(|p| p as u64)
            .collect(),
    })
}

/// Find the agent's `Report` anywhere in the response: a data part, or a text
/// part containing a JSON line.
fn find_report(v: &Value) -> Option<Report> {
    match v {
        Value::Object(map) => {
            if map.contains_key("elapsed_ms") {
                return report_from_object(v);
            }
            map.values().find_map(find_report)
        }
        Value::Array(a) => a.iter().find_map(find_report),
        Value::String(s) => s
            .lines()
            .filter(|l| l.trim_start().starts_with('{'))
            .find_map(|l| serde_json::from_str::<Value>(l).ok())
            .and_then(|j| report_from_object(&j)),
        _ => None,
    }
}

fn arg<T: std::str::FromStr>(args: &[String], name: &str, default: T) -> T {
    args.windows(2)
        .find(|w| w[0] == name)
        .and_then(|w| w[1].parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let min: usize = arg(&args, "--min", 1);
    let max: usize = arg(&args, "--max", 22);
    let reps: usize = arg(&args, "--reps", 5).max(1);
    let out: String = arg(&args, "--out", "results.json".to_string());

    let mut agents: Vec<(String, String)> = args
        .windows(2)
        .filter(|w| w[0] == "--agent")
        .filter_map(|w| {
            w[1].split_once('=')
                .map(|(a, b)| (a.to_string(), b.to_string()))
        })
        .collect();
    if agents.is_empty() {
        agents = vec![
            ("native".into(), "http://localhost:8104".into()),
            ("exec".into(), "http://localhost:8105".into()),
        ];
    }

    let resolver = AgentCardResolver::new(None);
    let factory = A2AClientFactory::builder().build();
    let mut rows = Vec::new();

    for (name, url) in &agents {
        let card = resolver.resolve(url).await?;
        let client = factory.create_from_card(&card).await?;
        eprintln!("{name}: {} @ {url}", card.name);

        // One untimed call per agent so connection setup is not in N=min.
        let warm = SendMessageRequest {
            message: Message::new(Role::User, vec![Part::text("first 1")]),
            configuration: None,
            metadata: None,
            tenant: None,
        };
        client.send_message(&warm).await?;

        for n in min..=max {
            let mut compute = Vec::with_capacity(reps);
            let mut rtt = Vec::with_capacity(reps);
            let mut overhead = Vec::with_capacity(reps);
            let mut found = 0;
            for _ in 0..reps {
                let req = SendMessageRequest {
                    message: Message::new(
                        Role::User,
                        vec![Part::text(format!(
                            "Calculate the first {n} Mersenne primes"
                        ))],
                    ),
                    configuration: None,
                    metadata: None,
                    tenant: None,
                };
                let t0 = Instant::now();
                let resp = client.send_message(&req).await?;
                let rtt_ms = t0.elapsed().as_secs_f64() * 1000.0;
                let body = serde_json::to_value(&resp)?;
                let report = find_report(&body)
                    .ok_or_else(|| format!("{name} N={n}: no report in response: {body}"))?;
                found = report.found;
                compute.push(report.elapsed_ms);
                rtt.push(rtt_ms);
                overhead.push(rtt_ms - report.elapsed_ms);
            }
            let row = Row {
                agent: name.clone(),
                n,
                found,
                reps,
                compute_ms_min: compute.iter().copied().fold(f64::INFINITY, f64::min),
                compute_ms_max: compute.iter().copied().fold(f64::NEG_INFINITY, f64::max),
                compute_ms_median: median(&mut compute),
                rtt_ms_min: rtt.iter().copied().fold(f64::INFINITY, f64::min),
                rtt_ms_max: rtt.iter().copied().fold(f64::NEG_INFINITY, f64::max),
                rtt_ms_median: median(&mut rtt),
                overhead_ms_median: median(&mut overhead),
            };
            eprintln!(
                "  N={:>2} found={:>2}  compute {:>11.4} ms  rtt {:>11.4} ms  overhead {:>8.4} ms",
                row.n, row.found, row.compute_ms_median, row.rtt_ms_median, row.overhead_ms_median
            );
            rows.push(row);
        }
    }

    // Side-by-side table: one line per N, one column group per agent.
    println!();
    print!("| N |");
    for (name, _) in &agents {
        print!(" {name} compute ms | {name} RTT ms | {name} overhead ms |");
    }
    println!();
    print!("|---|");
    for _ in &agents {
        print!("---:|---:|---:|");
    }
    println!();
    for n in min..=max {
        print!("| {n} |");
        for (name, _) in &agents {
            let r = rows.iter().find(|r| &r.agent == name && r.n == n).unwrap();
            print!(
                " {:.4} | {:.3} | {:.3} |",
                r.compute_ms_median, r.rtt_ms_median, r.overhead_ms_median
            );
        }
        println!();
    }

    std::fs::write(&out, serde_json::to_string_pretty(&rows)?)?;
    eprintln!(
        "\nwrote {} rows to {out} (medians of {reps} reps)",
        rows.len()
    );
    Ok(())
}
