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
//! Every call is validated before it counts: the report must answer the
//! question asked (`requested == N`, `found == min(N, 26)`), and when an LLM
//! is in the path (function-call parts in the history) it must have handed
//! the request to a sub-agent, so the timing cannot be model-written. A data
//! part is preferred over a JSON line in text. Each row records the report
//! source and the sub-agent the request was routed to.
//!
//! Usage: mersenne-bench [--min 1] [--max 26] [--reps 5] [--out results.json]
//!                       [--gap-ms 0] [--agent name=url ...]
//! --gap-ms idles before every timed call, to pace calls like a slower caller.
//! Default agents: native=http://localhost:8104  exec=http://localhost:8105

use std::time::Instant;

use a2a::*;
use a2a_benchmark_rust::{EXPONENTS, Report};
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
    /// "data" (structured data part) or "text" (JSON line in a text part).
    report_source: String,
    /// Sub-agent(s) an LLM coordinator transferred to; empty for direct calls.
    routed_to: Vec<String>,
}

/// What one response says, found by walking its JSON.
#[derive(Default)]
struct Scan {
    data_reports: Vec<Report>,
    text_reports: Vec<Report>,
    transfers: Vec<String>,
    llm_calls: usize,
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

/// Walk the response: reports in data parts, reports as JSON lines in text,
/// and function calls (ADK puts `{name, args}` / `{name, response}` in data
/// parts; `transfer_to_agent` names the sub-agent).
fn scan(v: &Value, out: &mut Scan) {
    match v {
        Value::Object(map) => {
            if map.contains_key("elapsed_ms") {
                if let Some(r) = report_from_object(v) {
                    out.data_reports.push(r);
                }
                return;
            }
            if let Some(name) = map.get("name").and_then(Value::as_str)
                && map.contains_key("args")
            {
                out.llm_calls += 1;
                if name == "transfer_to_agent"
                    && let Some(a) = map["args"].get("agent_name").and_then(Value::as_str)
                {
                    out.transfers.push(a.to_string());
                }
            }
            map.values().for_each(|x| scan(x, out));
        }
        Value::Array(a) => a.iter().for_each(|x| scan(x, out)),
        Value::String(s) => out.text_reports.extend(
            s.lines()
                .filter(|l| l.trim_start().starts_with('{'))
                .filter_map(|l| serde_json::from_str::<Value>(l).ok())
                .filter_map(|j| report_from_object(&j)),
        ),
        _ => {}
    }
}

/// The report for one call, validated against the question asked.
fn checked_report(body: &Value, n: usize) -> Result<(Report, &'static str, Vec<String>), String> {
    let mut s = Scan::default();
    scan(body, &mut s);
    if s.llm_calls > 0 && s.transfers.is_empty() {
        return Err("LLM in the path but no transfer_to_agent: timing may be model-written".into());
    }
    let (report, source) = match (s.data_reports.first(), s.text_reports.first()) {
        (Some(r), _) => (r.clone(), "data"),
        (None, Some(r)) => (r.clone(), "text"),
        (None, None) => return Err("no report in response".into()),
    };
    let want_found = n.min(EXPONENTS.len());
    if report.requested != n || report.found != want_found {
        return Err(format!(
            "report answers a different question: requested={} found={} (asked N={n}, expected found={want_found})",
            report.requested, report.found
        ));
    }
    s.transfers.dedup();
    Ok((report, source, s.transfers))
}

/// Four significant figures, so sub-microsecond medians never print as 0.
fn sig4(x: f64) -> String {
    if x == 0.0 || !x.is_finite() {
        return format!("{x}");
    }
    let decimals = (3 - x.abs().log10().floor() as i32).max(0) as usize;
    format!("{x:.decimals$}")
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
    let max: usize = arg(&args, "--max", EXPONENTS.len());
    let reps: usize = arg(&args, "--reps", 5).max(1);
    let out: String = arg(&args, "--out", "results.json".to_string());
    let gap = std::time::Duration::from_millis(arg(&args, "--gap-ms", 0u64));

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
            let mut sources: Vec<&str> = Vec::new();
            let mut routed: Vec<String> = Vec::new();
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
                if !gap.is_zero() {
                    tokio::time::sleep(gap).await;
                }
                let t0 = Instant::now();
                let resp = client.send_message(&req).await?;
                let rtt_ms = t0.elapsed().as_secs_f64() * 1000.0;
                let body = serde_json::to_value(&resp)?;
                let (report, source, transfers) =
                    checked_report(&body, n).map_err(|e| format!("{name} N={n}: {e}: {body}"))?;
                found = report.found;
                if !sources.contains(&source) {
                    sources.push(source);
                }
                for t in transfers {
                    if !routed.contains(&t) {
                        routed.push(t);
                    }
                }
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
                report_source: sources.join("+"),
                routed_to: routed,
            };
            eprintln!(
                "  N={:>2} found={:>2}  compute {:>11} ms  rtt {:>11.4} ms  overhead {:>8.4} ms  [{}{}]",
                row.n,
                row.found,
                sig4(row.compute_ms_median),
                row.rtt_ms_median,
                row.overhead_ms_median,
                row.report_source,
                if row.routed_to.is_empty() {
                    String::new()
                } else {
                    format!(" via {}", row.routed_to.join(","))
                }
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
                " {} | {:.3} | {:.3} |",
                sig4(r.compute_ms_median),
                r.rtt_ms_median,
                r.overhead_ms_median
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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn report(n: usize, found: usize) -> Value {
        json!({"requested": n, "found": found, "elapsed_ms": 0.5, "exponents": []})
    }

    #[test]
    fn direct_data_report_accepted() {
        let body = json!({"task": {"artifacts": [{"parts": [{"data": report(3, 3)}]}]}});
        let (r, src, via) = checked_report(&body, 3).unwrap();
        assert_eq!((r.found, src, via.len()), (3, "data", 0));
    }

    #[test]
    fn wrong_question_rejected() {
        let body = json!({"parts": [{"data": report(10, 10)}]});
        assert!(checked_report(&body, 11).is_err());
        let body = json!({"parts": [{"data": report(30, 30)}]}); // table has 26
        assert!(checked_report(&body, 30).is_err());
        let body = json!({"parts": [{"data": report(30, 26)}]});
        assert!(checked_report(&body, 30).is_ok());
    }

    #[test]
    fn llm_without_transfer_rejected() {
        let body = json!({"history": [
            {"parts": [{"data": {"name": "run_benchmark", "args": {}}}]},
            {"parts": [{"text": "{\"requested\":3,\"found\":3,\"elapsed_ms\":0.1,\"exponents\":[]}"}]}
        ]});
        assert!(checked_report(&body, 3).is_err());
        let body = json!({"history": [
            {"parts": [{"data": {"name": "transfer_to_agent", "args": {"agent_name": "native_rust_agent"}}}]},
            {"parts": [{"data": report(3, 3)}]}
        ]});
        let (_, src, via) = checked_report(&body, 3).unwrap();
        assert_eq!((src, via), ("data", vec!["native_rust_agent".to_string()]));
    }

    #[test]
    fn data_preferred_over_text() {
        let body = json!({"a": [{"text": "{\"requested\":3,\"found\":3,\"elapsed_ms\":9.0,\"exponents\":[]}"},
                                {"data": report(3, 3)}]});
        let (r, src, _) = checked_report(&body, 3).unwrap();
        assert_eq!((r.elapsed_ms, src), (0.5, "data"));
    }

    #[test]
    fn sig4_keeps_small_values() {
        assert_eq!(sig4(0.000439), "0.0004390");
        assert_eq!(sig4(0.0812), "0.08120");
        assert_eq!(sig4(181.174), "181.2");
        assert_eq!(sig4(2469.75), "2470");
    }
}
