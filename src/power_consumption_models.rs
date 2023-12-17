use super::aes;

pub trait ConsumptionModelTrait: Sync + Send {
    fn estimate(&self, payload: &[u8; 16], guess: u8, index: usize) -> f64;
}

pub struct ConsumptionModelRound0 {
    beta_modifier: f64,
}

pub struct ConsumptionModelRound1 {
    beta_modifier: f64,
    k0: [u8; 16], // Key of the first round
}

pub struct ConsumptionModelRound0DecTable {
    beta_modifier: f64,
}

pub struct ConsumptionModelRound1DecTable {
    beta_modifier: f64,
    tk0: [u8; 16], // Tweaked key of the first round
}

impl ConsumptionModelTrait for ConsumptionModelRound0 {
    fn estimate(&self, payload: &[u8; 16], guess: u8, index: usize) -> f64 {
        let p = aes::sbox(payload[index] ^ guess).count_ones() as f64;
        p.powf(self.beta_modifier)
    }
}

impl ConsumptionModelTrait for ConsumptionModelRound1 {
    fn estimate(&self, payload: &[u8; 16], guess: u8, index: usize) -> f64 {
        let mut aes_state = aes::AesState::new(payload);

        // Run the beginning of the first round
        aes_state.add_round_key(&self.k0);
        aes_state.sub_bytes();
        aes_state.shift_rows();
        aes_state.mix_columns();

        let p = (aes::sbox(aes_state.data[index] ^ guess)
            ^ aes::sbox(payload[index] ^ self.k0[index]))
        .count_ones() as f64;
        p.powf(self.beta_modifier)
    }
}

impl ConsumptionModelTrait for ConsumptionModelRound0DecTable {
    fn estimate(&self, payload: &[u8; 16], guess: u8, index: usize) -> f64 {
        let i = aes::inv_sbox(payload[index] ^ guess);
        let lut0: u32 = (aes::gal9(i) as u32)
            | ((aes::gal11(i) as u32) << 8)
            | ((aes::gal13(i) as u32) << 16)
            | ((aes::gal14(i) as u32) << 24);

        let p = lut0.count_ones() as f64;
        p.powf(self.beta_modifier)
    }
}

impl ConsumptionModelTrait for ConsumptionModelRound1DecTable {
    fn estimate(&self, payload: &[u8; 16], guess: u8, index: usize) -> f64 {
        // Run round0
        let mut aes_state = aes::AesState::new(payload);
        aes_state.add_round_key(&self.tk0);
        aes_state.shift_rows_inv();
        aes_state.sub_bytes_inv();
        aes_state.mix_columns_inv();

        let i = aes::inv_sbox(aes_state.data[index] ^ guess);
        let lut1: u32 = (aes::gal9(i) as u32)
            | ((aes::gal11(i) as u32) << 8)
            | ((aes::gal13(i) as u32) << 16)
            | ((aes::gal14(i) as u32) << 24);

        let p = lut1.count_ones() as f64;
        p.powf(self.beta_modifier)
    }
}

impl ConsumptionModelRound0 {
    pub fn new(beta_modifier: f64) -> Self {
        ConsumptionModelRound0 { beta_modifier }
    }
}

impl ConsumptionModelRound1 {
    pub fn new(k0: &[u8; 16], beta_modifier: f64) -> Self {
        ConsumptionModelRound1 {
            k0: *k0,
            beta_modifier,
        }
    }
}

impl ConsumptionModelRound0DecTable {
    pub fn new(beta_modifier: f64) -> Self {
        ConsumptionModelRound0DecTable { beta_modifier }
    }
}

impl ConsumptionModelRound1DecTable {
    pub fn new(tk0: &[u8; 16], beta_modifier: f64) -> Self {
        ConsumptionModelRound1DecTable {
            tk0: *tk0,
            beta_modifier,
        }
    }
}

pub fn state_hamming_weight(state: &[u8; 16]) -> f64 {
    state.iter().map(|c| c.count_ones() as f64).sum()
}
