use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::{
    exceptions::PyTypeError,
    prelude::*,
    types::{PyBytes, PyDict},
};

mod aes;
mod correlation_engine;
mod power_consumption_models;

use correlation_engine::OpenclCorrelationEngine;
use power_consumption_models::{
    state_hamming_weight, ConsumptionModelRound0, ConsumptionModelRound0DecTable,
    ConsumptionModelRound1, ConsumptionModelRound1DecTable, ConsumptionModelTrait,
};

#[pyclass]
struct CpaSolver {
    // Ciphertext inputs
    correlation_engine: Option<OpenclCorrelationEngine>,
    power_consumption_model: Box<dyn ConsumptionModelTrait>,
    k_index: usize,
}

fn get_power_consumption_model(
    name: &str,
    py_kwargs: Option<&PyDict>,
    beta_modifier: f64,
) -> PyResult<Box<dyn ConsumptionModelTrait>> {
    if name == "round0" {
        Ok(Box::new(ConsumptionModelRound0::new(beta_modifier)))
    } else if name == "round0dectable" {
        Ok(Box::new(ConsumptionModelRound0DecTable::new(beta_modifier)))
    } else if name == "round1" {
        let Some(args) = py_kwargs else
            {
                return Err(PyErr::new::<PyTypeError, _>("Missing argument k0"))
            };

        let Some(k0) = args.get_item("k0") else
            {
                return Err(PyErr::new::<PyTypeError, _>("Missing argument k0"))
            };

        let Ok(k0) = k0.downcast::<PyBytes>() else
            {
                return Err(PyErr::new::<PyTypeError, _>("k0 has invalid type"))
            };

        let Ok(k0_len) = k0.len() else
            {
                return Err(PyErr::new::<PyTypeError, _>("k0 has invalid len"))
            };

        if k0_len != 16 {
            return Err(PyErr::new::<PyTypeError, _>("k0 must be 16 bytes long"));
        }

        let k0 = k0.as_bytes();
        let k0: &[u8; 16] = k0.try_into().unwrap();

        Ok(Box::new(ConsumptionModelRound1::new(k0, beta_modifier)))
    } else if name == "round1dectable" {
        let Some(args) = py_kwargs else
            {
                return Err(PyErr::new::<PyTypeError, _>("Missing argument tk0"))
            };

        let Some(tk0) = args.get_item("tk0") else
            {
                return Err(PyErr::new::<PyTypeError, _>("Missing argument tk0"))
            };

        let Ok(tk0) = tk0.downcast::<PyBytes>() else
            {
                return Err(PyErr::new::<PyTypeError, _>("tk0 has invalid type"))
            };

        let Ok(tk0_len) = tk0.len() else
            {
                return Err(PyErr::new::<PyTypeError, _>("tk0 has invalid len"))
            };

        if tk0_len != 16 {
            return Err(PyErr::new::<PyTypeError, _>("tk0 must be 16 bytes long"));
        }

        let tk0 = tk0.as_bytes();
        let tk0: &[u8; 16] = tk0.try_into().unwrap();

        Ok(Box::new(ConsumptionModelRound1DecTable::new(
            tk0,
            beta_modifier,
        )))
    } else {
        return Err(PyErr::new::<PyTypeError, _>("Unknown model name"));
    }
}

#[pymethods]
impl CpaSolver {
    #[new]
    fn new(
        name: &str,
        k_index: usize,
        beta_modifier: f64,
        py_kwargs: Option<&PyDict>,
    ) -> PyResult<Self> {
        let power_consumption_model = get_power_consumption_model(name, py_kwargs, beta_modifier)?;

        let ret = CpaSolver {
            correlation_engine: None,
            power_consumption_model,
            k_index,
        };
        Ok(ret)
    }

    fn update(
        &mut self,
        payloads: Vec<[u8; 16]>,
        py_samples: PyReadonlyArray2<f64>,
    ) -> PyResult<()> {
        // Instantiate a correlation engine if needed
        if self.correlation_engine.is_none() {
            let duration = py_samples.shape()[1];
            let correlation_engine = match OpenclCorrelationEngine::new(duration, 256) {
                Ok(engine) => engine,
                Err(e) => {
                    let msg = format!("Cannot build correlation engine: {:?}", e);
                    return Err(PyErr::new::<PyTypeError, _>(msg));
                }
            };
            self.correlation_engine = Some(correlation_engine);
        }

        // Generated guesses for all possible bytes
        let guesses: Vec<Vec<f64>> = (0..=u8::MAX)
            .map(|i| {
                payloads
                    .iter()
                    .map(|c| self.power_consumption_model.estimate(c, i, self.k_index))
                    .collect()
            })
            .collect();

        let mut samples: Vec<Vec<f64>> = Vec::new();
        let py_samples = py_samples.as_array();

        for column in py_samples.columns() {
            let v = column.to_vec();
            samples.push(v);
        }

        let correlation_engine = self.correlation_engine.as_mut().unwrap();
        match correlation_engine.update(samples, guesses) {
            Ok(_) => Ok(()),
            Err(e) => {
                let msg = format!("Cannot update correlation engine: {:?}", e);
                Err(PyErr::new::<PyTypeError, _>(msg))
            }
        }
    }

    fn get_result(&self) -> PyResult<Py<PyArray2<f64>>> {
        if self.correlation_engine.is_none() {
            return Err(PyErr::new::<PyTypeError, _>("No results"));
        }
        let correlation_engine = self.correlation_engine.as_ref().unwrap();
        let result = match correlation_engine.get_result() {
            Ok(result) => result,
            Err(e) => {
                let msg = format!("Cannot get correlation results: {:?}", e);
                return Err(PyErr::new::<PyTypeError, _>(msg));
            }
        };

        let ret = Python::with_gil(|py| -> Py<PyArray2<f64>> {
            let test = PyArray2::from_vec2(py, &result).unwrap();
            test.to_owned()
        });

        Ok(ret)
    }
}

#[pyclass]
struct AssessmentSolver {
    correlation_engine: Option<OpenclCorrelationEngine>,
    keys: Vec<[u8; 16]>,
}

#[pymethods]
impl AssessmentSolver {
    #[new]
    fn new(keys: Vec<[u8; 16]>) -> PyResult<Self> {
        let ret = AssessmentSolver {
            correlation_engine: None,
            keys,
        };
        Ok(ret)
    }

    fn update(
        &mut self,
        payloads: Vec<[u8; 16]>,
        py_samples: PyReadonlyArray2<f64>,
    ) -> PyResult<()> {
        // Instantiate a correlation engine if needed
        if self.correlation_engine.is_none() {
            let duration = py_samples.shape()[1];

            // Check length of AES states power vector
            let dummy_payload = [0u8; 16];
            let dummy_states = aes::compute_all_states(&dummy_payload, &self.keys);
            let correlation_engine =
                match OpenclCorrelationEngine::new(duration, dummy_states.len()) {
                    Ok(engine) => engine,
                    Err(e) => {
                        let msg = format!("Cannot build correlation engine: {:?}", e);
                        return Err(PyErr::new::<PyTypeError, _>(msg));
                    }
                };
            self.correlation_engine = Some(correlation_engine);
        }

        // Generate power consumption values for all possible payloads
        let s_power_consumption: Vec<Vec<f64>> = payloads
            .iter()
            .map(|c| {
                aes::compute_all_states(c, &self.keys)
                    .iter()
                    .map(state_hamming_weight)
                    .collect()
            })
            .collect();

        // Swap axes
        let mut power_consumption: Vec<Vec<f64>> = Vec::new();
        for x in 0..s_power_consumption[0].len() {
            let v: Vec<f64> = (0..s_power_consumption.len())
                .map(|y| s_power_consumption[y][x])
                .collect();
            power_consumption.push(v);
        }

        let mut samples: Vec<Vec<f64>> = Vec::new();
        let py_samples = py_samples.as_array();

        for column in py_samples.columns() {
            let v = column.to_vec();
            samples.push(v);
        }

        let correlation_engine = self.correlation_engine.as_mut().unwrap();
        match correlation_engine.update(samples, power_consumption) {
            Ok(_) => Ok(()),
            Err(e) => {
                let msg = format!("Cannot update correlation engine: {:?}", e);
                Err(PyErr::new::<PyTypeError, _>(msg))
            }
        }
    }

    fn get_result(&self) -> PyResult<Py<PyArray2<f64>>> {
        if self.correlation_engine.is_none() {
            return Err(PyErr::new::<PyTypeError, _>("No results"));
        }
        let correlation_engine = self.correlation_engine.as_ref().unwrap();
        let result = match correlation_engine.get_result() {
            Ok(result) => result,
            Err(e) => {
                let msg = format!("Cannot get correlation results: {:?}", e);
                return Err(PyErr::new::<PyTypeError, _>(msg));
            }
        };

        let ret = Python::with_gil(|py| -> Py<PyArray2<f64>> {
            let test = PyArray2::from_vec2(py, &result).unwrap();
            test.to_owned()
        });

        Ok(ret)
    }
}

#[pymodule]
fn cpa_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<CpaSolver>()?;
    m.add_class::<AssessmentSolver>()?;

    Ok(())
}
