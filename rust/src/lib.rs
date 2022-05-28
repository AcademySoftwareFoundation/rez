use pyo3::prelude::*;

pub mod rez;

/// Formats the sum of two numbers as string.
#[pyfunction]
pub fn foo() -> PyResult<()> {
    rez::foo();

    Ok(())
}

/// A Python module implemented in Rust.
#[pymodule]
fn rez(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(foo, m)?)?;
    Ok(())
}
