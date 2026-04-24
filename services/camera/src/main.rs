use std::collections::HashMap;
use std::env;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use camera_service::{
    print_type_layout, CameraFrame, BLACKBOARD_KEY, CHANNELS, MAX_HEIGHT, MAX_WIDTH,
};
use iceoryx2::prelude::*;
use image::imageops::FilterType;
use image::RgbImage;
use v4l::buffer::Type;
use v4l::io::mmap::Stream as MmapStream;
use v4l::io::traits::CaptureStream;
use v4l::prelude::*;
use v4l::video::Capture;
use v4l::{FourCC, Fraction};

// ---------------------------------------------------------------------------
// Pixel format detected at startup
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq)]
enum PixelFormat {
    Mjpeg,
    Yuyv,
}

fn detect_and_configure(dev: &Device) -> PixelFormat {
    let formats = dev.enum_formats().expect("failed to enumerate formats");
    println!("[camera] available formats:");
    for f in &formats {
        println!("  {} — {}", f.fourcc, f.description);
    }

    let mjpeg = FourCC::new(b"MJPG");
    let yuyv = FourCC::new(b"YUYV");

    let chosen = if formats.iter().any(|f| f.fourcc == mjpeg) {
        PixelFormat::Mjpeg
    } else if formats.iter().any(|f| f.fourcc == yuyv) {
        PixelFormat::Yuyv
    } else {
        panic!(
            "[camera] no supported pixel format (need MJPEG or YUYV). camera offers: {:?}",
            formats
                .iter()
                .map(|f| f.fourcc.to_string())
                .collect::<Vec<_>>()
        );
    };

    // Set resolution + pixel format (capture at max resolution; resize happens later)
    let mut fmt = dev.format().expect("failed to get format");
    fmt.width = MAX_WIDTH;
    fmt.height = MAX_HEIGHT;
    fmt.fourcc = match chosen {
        PixelFormat::Mjpeg => mjpeg,
        PixelFormat::Yuyv => yuyv,
    };
    let fmt = dev.set_format(&fmt).expect("failed to set format");
    println!(
        "[camera] configured: {}x{} {:?} (driver set {}x{} {})",
        MAX_WIDTH, MAX_HEIGHT, chosen, fmt.width, fmt.height, fmt.fourcc
    );

    // Set frame rate
    let mut params = dev.params().expect("failed to get params");
    params.interval = Fraction::new(1, 30);
    let params = dev.set_params(&params).expect("failed to set params");
    println!(
        "[camera] fps: {}/{}",
        params.interval.denominator, params.interval.numerator
    );

    chosen
}

// ---------------------------------------------------------------------------
// YUYV → RGB conversion (fallback path)
// ---------------------------------------------------------------------------

fn yuyv_to_rgb(yuyv: &[u8], rgb: &mut [u8], width: u32, height: u32) {
    let npixels = (width * height) as usize;
    assert!(yuyv.len() >= npixels * 2, "YUYV buffer too small");
    assert!(rgb.len() >= npixels * 3, "RGB buffer too small");

    for i in 0..(npixels / 2) {
        let base = i * 4;
        let y0 = yuyv[base] as f32;
        let u = yuyv[base + 1] as f32 - 128.0;
        let y1 = yuyv[base + 2] as f32;
        let v = yuyv[base + 3] as f32 - 128.0;

        let r0 = (y0 + 1.402 * v).clamp(0.0, 255.0) as u8;
        let g0 = (y0 - 0.344136 * u - 0.714136 * v).clamp(0.0, 255.0) as u8;
        let b0 = (y0 + 1.772 * u).clamp(0.0, 255.0) as u8;

        let r1 = (y1 + 1.402 * v).clamp(0.0, 255.0) as u8;
        let g1 = (y1 - 0.344136 * u - 0.714136 * v).clamp(0.0, 255.0) as u8;
        let b1 = (y1 + 1.772 * u).clamp(0.0, 255.0) as u8;

        let out = i * 6;
        rgb[out] = r0;
        rgb[out + 1] = g0;
        rgb[out + 2] = b0;
        rgb[out + 3] = r1;
        rgb[out + 4] = g1;
        rgb[out + 5] = b1;
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Handle --type-check before any hardware/SHM initialization
    if env::args().nth(1).as_deref() == Some("--type-check") {
        print_type_layout();
        return Ok(());
    }

    // Parse IPC_PUBLISHES to get topic name (manifest-driven, not hardcoded)
    let ipc_publishes: HashMap<String, String> = serde_json::from_str(
        &env::var("IPC_PUBLISHES").unwrap_or_else(|_| "{}".into()),
    )?;

    let topic = ipc_publishes
        .iter()
        .find(|(_, type_name)| type_name.as_str() == "CameraFrame")
        .map(|(topic, _)| topic.clone())
        .expect(
            "[camera] IPC_PUBLISHES must contain an entry with type CameraFrame. \
             Set via services.yaml ipc.publishes or IPC_PUBLISHES env var.",
        );

    // Output resolution from env (infra param, set via services.yaml)
    let out_w: u32 = env::var("CAMERA_WIDTH")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(MAX_WIDTH);
    let out_h: u32 = env::var("CAMERA_HEIGHT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(MAX_HEIGHT);

    assert!(
        out_w <= MAX_WIDTH && out_h <= MAX_HEIGHT,
        "[camera] CAMERA_WIDTH/HEIGHT ({out_w}x{out_h}) exceeds max ({MAX_WIDTH}x{MAX_HEIGHT})"
    );

    let needs_resize = out_w != MAX_WIDTH || out_h != MAX_HEIGHT;
    println!(
        "[camera] output resolution: {}x{} (resize={})",
        out_w, out_h, needs_resize
    );

    let device_path = env::var("CAMERA_DEVICE").unwrap_or_else(|_| "/dev/video0".to_string());
    println!("[camera] opening {}", device_path);

    let dev = Device::with_path(&device_path)?;
    let pixel_fmt = detect_and_configure(&dev);

    // iceoryx2: create blackboard
    set_log_level_from_env_or(LogLevel::Warn);
    let node = NodeBuilder::new().create::<ipc::Service>()?;
    let service_name: ServiceName = topic.as_str().try_into()?;
    let initial = CameraFrame::default();

    let service = node
        .service_builder(&service_name)
        .blackboard_creator::<u64>()
        .add::<CameraFrame>(BLACKBOARD_KEY, initial)
        .create()?;

    let writer = service.writer_builder().create()?;
    let entry = writer.entry::<CameraFrame>(&BLACKBOARD_KEY)?;

    println!("[camera] iceoryx2 blackboard created on topic '{}'", topic);

    // MJPEG decompressor (reused across frames)
    let mut decompressor = turbojpeg::Decompressor::new()?;
    // Pre-allocate output image for turbojpeg decompress-into
    let capture_bytes = (MAX_WIDTH * MAX_HEIGHT * CHANNELS) as usize;
    let mut jpeg_output = turbojpeg::Image {
        pixels: vec![0u8; capture_bytes],
        width: MAX_WIDTH as usize,
        pitch: (MAX_WIDTH * CHANNELS) as usize,
        height: MAX_HEIGHT as usize,
        format: turbojpeg::PixelFormat::RGB,
    };

    // V4L2 MMAP stream — 4 buffers
    let mut stream = MmapStream::with_buffers(&dev, Type::VideoCapture, 4)?;

    // Warmup: discard first frame (often partial)
    let _ = stream.next();

    let mut frame_id: u64 = 0;
    let mut fps_counter: u32 = 0;
    let mut fps_timer = Instant::now();

    // Scratch buffer for full-resolution RGB
    let mut rgb_buf = vec![0u8; capture_bytes];

    println!("[camera] streaming...");

    loop {
        let (buf, _meta) = stream.next()?;

        let t_decode = Instant::now();

        // Decode to RGB at capture resolution
        match pixel_fmt {
            PixelFormat::Mjpeg => {
                decompressor.decompress(buf, jpeg_output.as_deref_mut())?;
                let n = jpeg_output.pixels.len().min(capture_bytes);
                rgb_buf[..n].copy_from_slice(&jpeg_output.pixels[..n]);
            }
            PixelFormat::Yuyv => {
                yuyv_to_rgb(buf, &mut rgb_buf, MAX_WIDTH, MAX_HEIGHT);
            }
        };

        // Resize if needed
        let (final_rgb, final_w, final_h) = if needs_resize {
            let src = RgbImage::from_raw(MAX_WIDTH, MAX_HEIGHT, rgb_buf.clone())
                .expect("failed to create image from RGB buffer");
            let resized = image::imageops::resize(&src, out_w, out_h, FilterType::Triangle);
            (resized.into_raw(), out_w, out_h)
        } else {
            (rgb_buf.clone(), MAX_WIDTH, MAX_HEIGHT)
        };

        let decode_us = t_decode.elapsed().as_micros();

        // Build SHM frame
        frame_id += 1;
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        let mut frame = CameraFrame::default();
        frame.timestamp = timestamp;
        frame.frame_id = frame_id;
        frame.width = final_w;
        frame.height = final_h;

        let n = (final_w * final_h * CHANNELS) as usize;
        frame.data[..n].copy_from_slice(&final_rgb[..n]);

        // Write to blackboard
        entry.update_with_copy(frame);

        // FPS logging
        fps_counter += 1;
        let elapsed = fps_timer.elapsed();
        if elapsed.as_secs() >= 1 {
            let fps = fps_counter as f64 / elapsed.as_secs_f64();
            println!(
                "[camera] fps={:.1}  frame_id={}  decode+resize={}us  out={}x{}",
                fps, frame_id, decode_us, final_w, final_h
            );
            fps_counter = 0;
            fps_timer = Instant::now();
        }
    }
}
