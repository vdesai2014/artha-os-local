use iceoryx2::prelude::*;

/// Maximum (and SHM struct) dimensions — the data array is always this big.
/// Actual capture resolution may be smaller; check width/height fields.
pub const MAX_WIDTH: u32 = 640;
pub const MAX_HEIGHT: u32 = 480;
pub const CHANNELS: u32 = 3;
pub const FRAME_BYTES: usize = (MAX_WIDTH * MAX_HEIGHT * CHANNELS) as usize;
pub const BLACKBOARD_KEY: u64 = 0;

#[derive(Debug, Clone, Copy, ZeroCopySend)]
#[repr(C)]
pub struct CameraFrame {
    pub timestamp: f64,
    pub frame_id: u64,
    pub width: u32,
    pub height: u32,
    pub channels: u32,
    pub _pad: u32,
    pub data: [u8; FRAME_BYTES],
}

impl Default for CameraFrame {
    fn default() -> Self {
        Self {
            timestamp: 0.0,
            frame_id: 0,
            width: MAX_WIDTH,
            height: MAX_HEIGHT,
            channels: CHANNELS,
            _pad: 0,
            data: [0u8; FRAME_BYTES],
        }
    }
}

/// Print struct layout info for supervisor type-check validation.
/// Output format is line-based, parsed by supervisor/_check_ipc_types().
pub fn print_type_layout() {
    println!(
        "TYPE CameraFrame SIZE {}",
        std::mem::size_of::<CameraFrame>()
    );
    println!(
        "FIELD timestamp OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, timestamp),
        std::mem::size_of::<f64>()
    );
    println!(
        "FIELD frame_id OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, frame_id),
        std::mem::size_of::<u64>()
    );
    println!(
        "FIELD width OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, width),
        std::mem::size_of::<u32>()
    );
    println!(
        "FIELD height OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, height),
        std::mem::size_of::<u32>()
    );
    println!(
        "FIELD channels OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, channels),
        std::mem::size_of::<u32>()
    );
    println!(
        "FIELD _pad OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, _pad),
        std::mem::size_of::<u32>()
    );
    println!(
        "FIELD data OFFSET {} SIZE {}",
        std::mem::offset_of!(CameraFrame, data),
        FRAME_BYTES
    );
}
