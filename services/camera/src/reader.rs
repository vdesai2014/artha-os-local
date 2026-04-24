use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::Write;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use camera_service::{CameraFrame, BLACKBOARD_KEY};
use iceoryx2::prelude::*;

const DEFAULT_IPC_SUBSCRIBES: &str = r#"{"camera/rgb": "CameraFrame"}"#;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    set_log_level_from_env_or(LogLevel::Warn);

    // Parse IPC_SUBSCRIBES to get topic name (falls back to default for standalone use)
    let ipc_subscribes: HashMap<String, String> = serde_json::from_str(
        &env::var("IPC_SUBSCRIBES").unwrap_or_else(|_| DEFAULT_IPC_SUBSCRIBES.into()),
    )?;

    let topic = ipc_subscribes
        .iter()
        .find(|(_, type_name)| type_name.as_str() == "CameraFrame")
        .map(|(topic, _)| topic.clone())
        .expect(
            "[reader] IPC_SUBSCRIBES must contain an entry with type CameraFrame",
        );

    let node = NodeBuilder::new().create::<ipc::Service>()?;
    let service_name: ServiceName = topic.as_str().try_into()?;

    println!("[reader] opening blackboard '{}'...", topic);

    let service = node
        .service_builder(&service_name)
        .blackboard_opener::<u64>()
        .open()?;

    let reader = service.reader_builder().create()?;
    let entry = reader.entry::<CameraFrame>(&BLACKBOARD_KEY)?;

    println!("[reader] connected. reading frames...");

    let mut last_frame_id: u64 = 0;
    let mut ppm_dumped = false;
    let mut fps_counter: u32 = 0;
    let mut fps_timer = Instant::now();
    let poll_interval = Duration::from_millis(5); // 200Hz poll

    loop {
        let frame: CameraFrame = *entry.get();

        if frame.frame_id != last_frame_id {
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs_f64();
            let latency_ms = (now - frame.timestamp) * 1000.0;

            fps_counter += 1;
            let elapsed = fps_timer.elapsed();
            if elapsed.as_secs() >= 1 {
                let fps = fps_counter as f64 / elapsed.as_secs_f64();

                // Check first 100 bytes are non-zero
                let nonzero = frame.data[..100].iter().filter(|&&b| b != 0).count();

                println!(
                    "[reader] fps={:.1}  frame_id={}  latency={:.2}ms  nonzero_100={}/100  {}x{}",
                    fps, frame.frame_id, latency_ms, nonzero, frame.width, frame.height
                );
                fps_counter = 0;
                fps_timer = Instant::now();
            }

            // Dump first valid frame to PPM for visual verification
            if !ppm_dumped && frame.frame_id > 2 {
                let path = "test_frame.ppm";
                let mut f = File::create(path)?;
                write!(f, "P6\n{} {}\n255\n", frame.width, frame.height)?;
                let nbytes = (frame.width * frame.height * frame.channels) as usize;
                f.write_all(&frame.data[..nbytes])?;
                println!("[reader] dumped frame {} to {}", frame.frame_id, path);
                ppm_dumped = true;
            }

            last_frame_id = frame.frame_id;
        }

        std::thread::sleep(poll_interval);
    }
}
