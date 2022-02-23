use super::utils::{Common, VersionError};
use std::cmp::Eq;
use std::collections::VecDeque;
use std::str::FromStr;
use std::string::ToString;

macro_rules! regex {
    ($re:literal $(,)?) => {{
        static RE: once_cell::sync::OnceCell<regex::Regex> = once_cell::sync::OnceCell::new();
        RE.get_or_init(|| regex::Regex::new($re).unwrap())
    }};
}

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

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
struct SubToken {
    s: String,
    n: Option<u64>,
}

impl Common for SubToken {}
impl Comparable for SubToken {}

impl ToString for SubToken {
    fn to_string(&self) -> String {
        self.s.clone()
    }
}

impl FromStr for SubToken {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(Self::new(s))
    }
}

impl SubToken {
    pub fn new(s: &str) -> Self {
        Self {
            s: s.to_string(),
            n: match s.parse() {
                Ok(n) => Some(n),
                Err(_) => None,
            },
        }
    }
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
struct AlphanumericVersionToken {
    subtokens: Option<Vec<SubToken>>,
}

impl Common for AlphanumericVersionToken {}

impl Comparable for AlphanumericVersionToken {}

impl VersionToken for AlphanumericVersionToken {}

impl ToString for AlphanumericVersionToken {
    fn to_string(&self) -> String {
        match &self.subtokens {
            Some(subtokens) => subtokens
                .iter()
                .map(|subtoken| subtoken.to_string())
                .collect::<Vec<String>>()
                .concat(),
            None => "".to_string(),
        }
    }
}

impl FromStr for AlphanumericVersionToken {
    type Err = VersionError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::new(Some(s))
    }
}

impl Iterator for AlphanumericVersionToken {
    type Item = AlphanumericVersionToken;

    fn next(&mut self) -> Option<Self::Item> {
        let mut other = Self::new(None).unwrap();

        // TODO: Not sure if we should return out of the iterator at this point,
        // or just fail.
        let mut subtokens = match &self.subtokens {
            Some(subtokens) => subtokens.to_vec(),
            None => return None,
        };

        match subtokens.iter_mut().last() {
            Some(subtoken) => {
                if subtoken.n.is_none() {
                    *subtoken = SubToken::from_str(&format!("{}_", subtoken.s)).unwrap()
                } else {
                    subtokens.push(SubToken::from_str("_").unwrap())
                }
            }
            None => return None,
        };

        other.subtokens = Some(subtokens);

        Some(other)
    }
}

impl AlphanumericVersionToken {
    pub fn new(token: Option<&str>) -> Result<Self, VersionError> {
        let subtokens = match token {
            Some(t) => {
                if Self::regex().is_match(t) {
                    return Err(VersionError::new(&format!(
                        "Invalid version token: '{}'",
                        t
                    )));
                } else {
                    Some(Self::parse(t))
                }
            }
            None => None,
        };

        Ok(Self { subtokens })
    }

    fn regex() -> &'static regex::Regex {
        regex!(r#"[a-zA-Z0-9_]+\Z"#)
    }

    fn numeric_regex() -> &'static regex::Regex {
        regex!(r#"[0-9]+"#)
    }

    fn parse(token: &str) -> Vec<SubToken> {
        let mut subtokens = Vec::new();
        let mut alphas: VecDeque<&str> = Self::numeric_regex().split(token).collect();
        let mut numerics: VecDeque<&str> = Self::numeric_regex()
            .find_iter(token)
            .map(|m| m.as_str())
            .collect();
        let mut b = true;

        while !alphas.is_empty() || !numerics.is_empty() {
            if b {
                let alpha = alphas.pop_front().unwrap();

                if !alpha.is_empty() {
                    subtokens.push(SubToken::new(alpha))
                }
            } else {
                let numeric = numerics.pop_front().unwrap();

                if !numeric.is_empty() {
                    subtokens.push(SubToken::new(numeric))
                }
            }

            b = !b;
        }

        subtokens
    }
}

#[derive(Debug)]
pub struct Version {}

#[derive(Debug)]
pub struct VersionRange {}
