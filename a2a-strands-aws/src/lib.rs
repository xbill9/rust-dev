//! Mersenne prime workload shared by every binary in this crate.
//!
//! The workload matches `~/a2a-benchmark`: for the first `count` known
//! Mersenne exponents, confirm each one with the Lucas-Lehmer test and
//! report how long the whole run took.

use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde::{Deserialize, Serialize};
use std::time::Instant;

/// The first 26 Mersenne prime exponents (same table as `~/a2a-benchmark`).
pub const EXPONENTS: [u64; 26] = [
    2, 3, 5, 7, 13, 17, 19, 31, 61, 89, 107, 127, 521, 607, 1279, 2203, 2281, 3217, 4253, 4423,
    9689, 9941, 11213, 19937, 21701, 23209,
];

/// Count used when the request carries no number.
pub const DEFAULT_COUNT: usize = 5;

/// Structured result of one run. Serialised into the A2A data artifact and
/// into the JSON line printed by `mersenne-exec`, so clients read timing
/// from a field instead of parsing prose.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Report {
    pub requested: usize,
    pub found: usize,
    pub elapsed_ms: f64,
    pub exponents: Vec<u64>,
}

impl Report {
    /// One-line summary in the format the `~/a2a-benchmark` runner parses.
    pub fn summary(&self) -> String {
        format!(
            "Found first {} Mersenne primes in {:.4}ms.",
            self.found, self.elapsed_ms
        )
    }
}

/// Lucas-Lehmer test for M_p = 2^p - 1, with p prime.
pub fn is_mersenne_prime(p: u64) -> bool {
    if p == 2 {
        return true;
    }
    let p_us = p as usize;
    let m_p: BigUint = (BigUint::one() << p_us) - BigUint::one();
    let two = BigUint::from(2u32);
    let mut s = BigUint::from(4u32);
    for _ in 0..(p - 2) {
        s = &s * &s;
        // s >= 2 always holds after squaring (s starts at 4 and is reduced to
        // at most m_p), so the subtraction cannot underflow except when s was 0.
        s = if s >= two { s - &two } else { &s + &m_p - &two };
        // Fast reduction mod 2^p - 1: fold the high bits onto the low bits.
        while s > m_p {
            s = (&s >> p_us) + (&s & &m_p);
        }
        if s == m_p {
            s = BigUint::zero();
        }
    }
    s.is_zero()
}

/// Confirm the first `count` exponents (capped at the table length) and time it
/// with a monotonic clock. Only the computation is inside the timed region.
pub fn find_mersenne_primes(count: usize) -> Report {
    let start = Instant::now();
    let mut exponents = Vec::with_capacity(count.min(EXPONENTS.len()));
    for &p in EXPONENTS.iter().take(count) {
        if is_mersenne_prime(p) {
            exponents.push(p);
        }
    }
    let elapsed_ms = start.elapsed().as_secs_f64() * 1000.0;
    Report {
        requested: count,
        found: exponents.len(),
        elapsed_ms,
        exponents,
    }
}

/// First positive integer in `text`, or `None`. A number too large for
/// `usize` saturates to `usize::MAX` (the run is capped by the exponent table
/// anyway) instead of being skipped, which used to fall back to the default.
pub fn parse_count(text: &str) -> Option<usize> {
    text.split(|c: char| !c.is_ascii_digit())
        .filter(|s| !s.is_empty())
        .map(|s| s.parse::<usize>().unwrap_or(usize::MAX))
        .find(|&n| n > 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_exponents_are_prime() {
        for &p in &EXPONENTS[..15] {
            assert!(is_mersenne_prime(p), "M_{p} should be prime");
        }
    }

    #[test]
    fn composite_mersenne_rejected() {
        // 2^11 - 1 = 2047 = 23 * 89, 2^23 - 1 = 47 * 178481
        assert!(!is_mersenne_prime(11));
        assert!(!is_mersenne_prime(23));
        assert!(!is_mersenne_prime(29));
    }

    #[test]
    fn report_counts_what_was_found() {
        let r = find_mersenne_primes(40);
        assert_eq!(r.requested, 40);
        assert_eq!(r.found, EXPONENTS.len());
        let r = find_mersenne_primes(5);
        assert_eq!(r.exponents, vec![2, 3, 5, 7, 13]);
    }

    #[test]
    fn parses_first_positive_number() {
        assert_eq!(
            parse_count("Calculate the first 12 Mersenne primes"),
            Some(12)
        );
        assert_eq!(parse_count("0 then 7"), Some(7));
        assert_eq!(parse_count("no digits"), None);
        assert_eq!(parse_count("000 then 3"), Some(3));
    }

    #[test]
    fn oversized_count_saturates() {
        assert_eq!(
            parse_count("first 99999999999999999999999"),
            Some(usize::MAX)
        );
    }

    /// Exhaustive check through N=22 (exponent 9941): Lucas-Lehmer must
    /// accept exactly the first 22 table entries among *all* primes p <= 9941.
    /// Slow (tens of seconds): cargo test --release -- --ignored
    #[test]
    #[ignore]
    fn exhaustive_through_n22() {
        let limit = EXPONENTS[21];
        let sieve = {
            let mut is = vec![true; (limit + 1) as usize];
            is[0] = false;
            is[1] = false;
            let mut i = 2;
            while i * i <= limit as usize {
                if is[i] {
                    (i * i..=limit as usize)
                        .step_by(i)
                        .for_each(|j| is[j] = false);
                }
                i += 1;
            }
            is
        };
        let found: Vec<u64> = (2..=limit)
            .filter(|&p| sieve[p as usize] && is_mersenne_prime(p))
            .collect();
        assert_eq!(found, EXPONENTS[..22].to_vec());
    }

    /// All 26 table entries pass. Slow: cargo test --release -- --ignored
    #[test]
    #[ignore]
    fn all_26_exponents_prime() {
        assert_eq!(find_mersenne_primes(26).found, 26);
    }
}
