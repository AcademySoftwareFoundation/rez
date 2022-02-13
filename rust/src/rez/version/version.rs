use super::utils::{Common, VersionError};
use std::cmp::Eq;
use std::str::FromStr;
use std::string::ToString;

trait Comparable: Common + Ord {}

#[derive(Debug, PartialEq, Eq)]
struct ReversedComparable<T: Comparable> {
    item: T,
}

impl<T: Comparable> PartialOrd for ReversedComparable<T> {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl<T: Comparable> Ord for ReversedComparable<T> {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        match self.item.cmp(&other.item) {
            std::cmp::Ordering::Less => std::cmp::Ordering::Greater,
            std::cmp::Ordering::Equal => std::cmp::Ordering::Equal,
            std::cmp::Ordering::Greater => std::cmp::Ordering::Less,
        }
    }
}

impl<T: Comparable> ToString for ReversedComparable<T> {
    fn to_string(&self) -> String {
        self.item.to_string()
    }
}

impl<T: Comparable> Common for ReversedComparable<T> {}

impl<T: Comparable> Comparable for ReversedComparable<T> {}

impl<T: Comparable> ReversedComparable<T> {
    pub fn new(item: T) -> Self {
        Self { item }
    }
}

trait VersionToken: Comparable + FromStr + Iterator {}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
struct NumericToken {
    n: u64,
}

impl Common for NumericToken {}

impl Comparable for NumericToken {}

impl VersionToken for NumericToken {}

impl ToString for NumericToken {
    fn to_string(&self) -> String {
        self.n.to_string()
    }
}

impl FromStr for NumericToken {
    type Err = VersionError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let n = match s.parse() {
            Ok(n) => n,
            Err(_) => {
                return Err(VersionError::new(&format!(
                    "Invalid version token: '{}'",
                    s
                )))
            }
        };

        Ok(Self { n })
    }
}

impl Iterator for NumericToken {
    type Item = NumericToken;

    fn next(&mut self) -> Option<Self::Item> {
        Some(Self { n: self.n + 1 })
    }
}

impl NumericToken {
    pub fn new(n: u64) -> Self {
        Self { n }
    }
}

#[derive(Debug)]
pub struct Version {}

#[derive(Debug)]
pub struct VersionRange {}
