use super::utils::{Common, VersionError};
use std::cmp::Eq;
use std::collections::VecDeque;
use std::hash::Hash;
use std::ops::Index;
use std::str::FromStr;
use std::string::ToString;

macro_rules! regex {
    ($re:literal $(,)?) => {{
        static RE: once_cell::sync::OnceCell<regex::Regex> = once_cell::sync::OnceCell::new();
        RE.get_or_init(|| regex::Regex::new($re).unwrap())
    }};
}

pub trait Comparable: Common + Ord {}

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

pub trait VersionToken: Comparable + FromStr + Iterator {}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct NumericToken {
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
pub struct AlphanumericVersionToken {
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

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
enum VersionState {
    Finite,
    Infinite,
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
pub struct Version<T: VersionToken> {
    state: VersionState,
    tokens: Vec<T>,
    seps: Vec<String>,
}

impl<T: VersionToken> Common for Version<T> {}

impl<T: VersionToken> Comparable for Version<T> {}

impl<T: VersionToken> Default for Version<T> {
    fn default() -> Self {
        Self {
            state: VersionState::Finite,
            tokens: Vec::new(),
            seps: Vec::new(),
        }
    }
}

impl<T: VersionToken> ToString for Version<T> {
    fn to_string(&self) -> String {
        if self.state == VersionState::Infinite {
            "[INF]".to_string()
        } else {
            let mut seps = self.seps.clone();
            seps.push("".to_string());

            let joined_tokens: String = self
                .tokens
                .iter()
                .map(|t| t.to_string())
                .zip(seps)
                .map(|(x, y)| x + &y)
                .collect();

            joined_tokens
        }
    }
}

impl<T> Iterator for Version<T>
where
    <T as FromStr>::Err: std::fmt::Display,
    T: VersionToken + std::clone::Clone + Iterator<Item = T>,
{
    type Item = Version<T>;

    fn next(&mut self) -> Option<Self::Item> {
        if !self.tokens.is_empty() {
            let mut other = self.clone();

            // TODO: What to do if the tokens vec is empty?
            let mut token = other.tokens.pop().unwrap();
            other.tokens.push(token.next().unwrap());

            Some(other)
        } else {
            Some(Self::infinity())
        }
    }
}

impl<T> Index<usize> for Version<T>
where
    T: VersionToken,
{
    type Output = T;

    fn index(&self, index: usize) -> &Self::Output {
        &self.tokens[index]
    }
}

impl<T> Hash for Version<T>
where
    T: VersionToken,
{
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        for token in &self.tokens {
            token.to_string().hash(state);
        }
    }
}

impl<T> Version<T>
where
    <T as FromStr>::Err: std::fmt::Display,
    T: VersionToken,
    // T: VersionToken + std::clone::Clone,
{
    pub fn new(version: &str) -> Result<Self, VersionError> {
        let mut tokens = Vec::new();

        let raw_tokens: Vec<&str> = Self::regex()
            .find_iter(version)
            .map(|m| m.as_str())
            .collect();

        if raw_tokens.is_empty() {
            return Err(VersionError::new(version));
        }

        let seps: Vec<String> = Self::regex()
            .split(version)
            .map(|s| s.to_string())
            .collect();

        // Note: The unwraps for the seps below should not panic, since we are
        // guaranteeing that the seps vec has something in it.
        if seps.is_empty() {
            return Err(VersionError::new(version));
        }

        if !seps[0].is_empty()
            || !seps.iter().last().unwrap().is_empty()
            || seps.iter().map(|s| s.len()).max().unwrap() > 1
        {
            return Err(VersionError::new(&format!(
                "Invalid version syntax: '{}'",
                version
            )));
        }

        for raw_token in raw_tokens {
            match T::from_str(raw_token) {
                Ok(t) => tokens.push(t),
                Err(err) => {
                    return Err(VersionError::new(&format!(
                        "Invalid version '{}': {}",
                        version, err
                    )))
                }
            }
        }

        Ok(Self {
            state: VersionState::Finite,
            tokens,
            seps: seps[1..].to_vec(),
        })
    }
}

impl<T> Version<T>
where
    T: VersionToken + std::clone::Clone,
{
    pub fn trim(self, len: usize) -> Self {
        let mut other = Self::default();
        other.tokens = self.tokens[..len].to_vec();
        // TODO: What to do if len <= 0?
        other.seps = self.seps[..len - 1].to_vec();

        other
    }
}

impl<T> Version<T>
where
    T: VersionToken,
{
    pub fn infinity() -> Self {
        let mut version = Self::default();
        version.state = VersionState::Infinite;

        version
    }

    pub fn major(&self) -> &T {
        &self.tokens[0]
    }

    pub fn minor(&self) -> &T {
        &self.tokens[1]
    }

    pub fn patch(&self) -> &T {
        &self.tokens[2]
    }

    pub fn as_tuple(&self) -> (&T, &T, &T) {
        (self.major(), self.minor(), self.patch())
    }

    pub fn len(&self) -> usize {
        self.tokens.len()
    }

    pub fn is_empty(&self) -> bool {
        self.tokens.is_empty()
    }

    fn regex() -> &'static regex::Regex {
        regex!(r#"[a-zA-Z0-9_]+"#)
    }
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
struct LowerBound<T: VersionToken> {
    version: Version<T>,
    inclusive: bool,
}

impl<T: VersionToken> Common for LowerBound<T> {}

impl<T: VersionToken> Comparable for LowerBound<T> {}

impl<T: VersionToken> ToString for LowerBound<T> {
    fn to_string(&self) -> String {
        if !self.version.is_empty() {
            if self.inclusive {
                format!("{}+", self.version.to_string())
            } else {
                format!(">{}", self.version.to_string())
            }
        } else {
            if self.inclusive {
                "".to_string()
            } else {
                ">".to_string()
            }
        }
    }
}

impl<T: VersionToken> Hash for LowerBound<T> {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.version.hash(state);
        self.inclusive.hash(state);
    }
}

impl<T: VersionToken> LowerBound<T> {
    pub fn new(version: Version<T>, inclusive: bool) -> Self {
        Self { version, inclusive }
    }

    pub fn min() -> Self {
        Self::new(Version::default(), true)
    }

    pub fn contains_version(&self, version: Version<T>) -> bool {
        (version > self.version) || (self.inclusive && (version == self.version))
    }
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord, Clone)]
struct UpperBound<T: VersionToken> {
    version: Version<T>,
    inclusive: bool,
}

impl<T: VersionToken> Common for UpperBound<T> {}

impl<T: VersionToken> Comparable for UpperBound<T> {}

impl<T: VersionToken> ToString for UpperBound<T> {
    fn to_string(&self) -> String {
        if self.inclusive {
            format!("<={}", self.version.to_string())
        } else {
            format!("<{}", self.version.to_string())
        }
    }
}

impl<T: VersionToken> Hash for UpperBound<T> {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.version.hash(state);
        self.inclusive.hash(state);
    }
}

impl<T: VersionToken> UpperBound<T> {
    pub fn new(version: Version<T>, inclusive: bool) -> Result<Self, VersionError> {
        let upper_bound = Self { version, inclusive };

        if upper_bound.version.is_empty() && !inclusive {
            return Err(VersionError::new(&format!(
                "Invalid upper bound: '{}'",
                upper_bound.to_string()
            )));
        }

        Ok(upper_bound)
    }

    pub fn infinity() -> Self {
        Self::new(Version::infinity(), true).unwrap()
    }

    pub fn contains_version(&self, version: Version<T>) -> bool {
        (version < self.version) || (self.inclusive && (version == self.version))
    }
}

#[derive(Debug)]
pub struct VersionRange {}

fn reverse_sort_key<T: Comparable>(comparable: T) -> ReversedComparable<T> {
    ReversedComparable::new(comparable)
}
