use cpython::{py_fn, py_module_initializer, PyNone, PyResult, Python};
use rez;

py_module_initializer!(rez, |py, m| {
    m.add(py, "__doc__", "Module documentation string")?;
    m.add(py, "foo", py_fn!(py, foo()))?;

    Ok(())
});

fn foo(_: Python) -> PyResult<PyNone> {
    rez::foo();

    Ok(PyNone)
}
