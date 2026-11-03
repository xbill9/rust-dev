//! A2A-unaware Mersenne prime program for `a2a server --exec`.
//!
//! Reads the user's message on stdin, prints the summary line and then one
//! JSON line with the structured report. Knows nothing about A2A: the
//! `a2a` CLI wraps it (Step 3 of the A2A CLI introduction):
//!
//!   a2a server --exec "target/release/mersenne-exec" --port 8105

use std::io::{Read, Write};

use a2a_benchmark_rust::{DEFAULT_COUNT, find_mersenne_primes, parse_count};

fn main() {
    let mut input = String::new();
    if let Err(e) = std::io::stdin().read_to_string(&mut input) {
        eprintln!("mersenne-exec: cannot read stdin: {e}");
        std::process::exit(1);
    }
    let count = parse_count(&input).unwrap_or(DEFAULT_COUNT);
    let report = find_mersenne_primes(count);

    let mut out = std::io::stdout().lock();
    let json = serde_json::to_string(&report).expect("report serialises");
    writeln!(out, "{}", report.summary())
        .and_then(|_| writeln!(out, "{json}"))
        .ok();
}
