use ocl::{Buffer, MemFlags, ProQue};
use std::error::Error;

pub struct OpenclCorrelationEngine {
    pro_queue: ProQue,
    kernel: ocl::Kernel,
    result_buffer: Buffer<f64>,
    last_n: usize,
    sample_duration: usize,
    n_guesses: usize
}

impl OpenclCorrelationEngine {
    pub fn new(sample_duration: usize, n_guesses: usize) -> Result<Self, Box<dyn Error>> {
        let src = include_str!("correlation.cl");

        let pro_queue = ProQue::builder()
            .src(src)
            .dims((n_guesses, sample_duration))
            .build()?;

        //
        // Allocate result and state buffers
        //

        let result_buffer = pro_queue.create_buffer::<f64>()?;
        let mx_buffer = pro_queue.create_buffer::<f64>()?;
        let my_buffer = pro_queue.create_buffer::<f64>()?;
        let mmx_buffer = pro_queue.create_buffer::<f64>()?;
        let mmy_buffer = pro_queue.create_buffer::<f64>()?;
        let c_buffer = pro_queue.create_buffer::<f64>()?;

        //
        // Build kernel
        //

        let kernel = pro_queue
            .kernel_builder("compute_correlations")
            .arg_named("samples", None::<&Buffer<f64>>)
            .arg_named("guesses", None::<&Buffer<f64>>)
            .arg(&result_buffer)
            .arg(&mx_buffer)
            .arg(&my_buffer)
            .arg(&mmx_buffer)
            .arg(&mmy_buffer)
            .arg(&c_buffer)
            .arg_named("n_samples", 0_u32)
            .arg_named("last_n", 0_u32)
            .build()?;

        let ret = OpenclCorrelationEngine {
            pro_queue,
            kernel,
            result_buffer,
            last_n: 0,
            sample_duration,
            n_guesses
        };

        Ok(ret)
    }

    pub fn update(
        &mut self,
        samples: Vec<Vec<f64>>,
        guesses: Vec<Vec<f64>>,
    ) -> Result<(), Box<dyn Error>> {
        //
        // Generate samples buffer
        //

        let n_samples = samples[0].len();

        // Flatten buffer
        let samples_vec: Vec<f64> = samples.into_iter().flatten().collect();

        let samples_buffer = Buffer::builder()
            .queue(self.pro_queue.queue().clone())
            .flags(MemFlags::new().read_only())
            .len((self.sample_duration, n_samples))
            .copy_host_slice(&samples_vec)
            .build()?;

        self.kernel.set_arg("samples", samples_buffer)?;
        self.kernel.set_arg("n_samples", n_samples as u32)?;

        //
        // Generate guesses buffer
        //

        // Flatten vector
        let guesses: Vec<f64> = guesses.into_iter().flatten().collect();

        let guesses_buffer = Buffer::builder()
            .queue(self.pro_queue.queue().clone())
            .flags(MemFlags::new().read_only())
            .len((self.n_guesses, n_samples))
            .copy_host_slice(&guesses)
            .build()?;

        self.kernel.set_arg("guesses", guesses_buffer)?;

        self.kernel.set_arg("last_n", self.last_n as u32)?;
        self.last_n += n_samples;

        unsafe {
            self.kernel.enq()?;
        }

        Ok(())
    }

    pub fn get_result(&self) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
        let mut result = vec![0.0f64; self.result_buffer.len()];
        self.result_buffer.read(&mut result).enq()?;

        let result: Vec<Vec<f64>> = result
            .chunks(self.sample_duration)
            .map(|v| v.to_owned())
            .collect();

        Ok(result)
    }
}
