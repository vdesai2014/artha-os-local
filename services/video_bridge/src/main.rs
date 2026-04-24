use std::collections::HashMap;
use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use camera_service::{CameraFrame, BLACKBOARD_KEY};
use iceoryx2::prelude::*;

// ---------------------------------------------------------------------------
// MJPEG streaming to a single client
// ---------------------------------------------------------------------------

fn stream_mjpeg(
    stream: &mut impl Write,
    topic: &str,
    quality: i32,
    frame_interval: Duration,
    shutdown: &AtomicBool,
) {
    // Open iceoryx2 blackboard reader
    let node = match NodeBuilder::new().create::<ipc::Service>() {
        Ok(n) => n,
        Err(e) => {
            eprintln!("[video_bridge] node error: {e:?}");
            return;
        }
    };

    let service_name: ServiceName = match topic.try_into() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[video_bridge] bad topic '{topic}': {e:?}");
            return;
        }
    };

    let service = match node
        .service_builder(&service_name)
        .blackboard_opener::<u64>()
        .open()
    {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[video_bridge] can't open '{topic}': {e:?}");
            return;
        }
    };

    let reader = match service.reader_builder().create() {
        Ok(r) => r,
        Err(e) => {
            eprintln!("[video_bridge] reader error: {e:?}");
            return;
        }
    };

    let entry = match reader.entry::<CameraFrame>(&BLACKBOARD_KEY) {
        Ok(e) => e,
        Err(e) => {
            eprintln!("[video_bridge] entry error: {e:?}");
            return;
        }
    };

    let mut compressor = match turbojpeg::Compressor::new() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("[video_bridge] compressor error: {e}");
            return;
        }
    };
    let _ = compressor.set_quality(quality);

    let mut last_frame_id: u64 = 0;
    let mut next_send = Instant::now();

    while !shutdown.load(Ordering::Relaxed) {
        let frame: CameraFrame = *entry.get();

        if frame.frame_id == last_frame_id || frame.frame_id == 0 {
            thread::sleep(Duration::from_millis(1));
            continue;
        }
        last_frame_id = frame.frame_id;

        // Rate limit: skip if we're ahead of schedule
        let now = Instant::now();
        if now < next_send {
            continue;
        }
        next_send = now + frame_interval;

        let w = frame.width as usize;
        let h = frame.height as usize;
        let n_bytes = w * h * 3;

        if n_bytes == 0 || n_bytes > frame.data.len() {
            continue;
        }

        // JPEG encode
        let src = turbojpeg::Image {
            pixels: &frame.data[..n_bytes],
            width: w,
            pitch: w * 3,
            height: h,
            format: turbojpeg::PixelFormat::RGB,
        };

        let jpeg = match compressor.compress_to_vec(src) {
            Ok(j) => j,
            Err(e) => {
                eprintln!("[video_bridge] compress error: {e}");
                continue;
            }
        };

        // Write MJPEG multipart chunk
        let chunk = format!(
            "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {}\r\n\r\n",
            jpeg.len()
        );
        if stream.write_all(chunk.as_bytes()).is_err() {
            break;
        }
        if stream.write_all(&jpeg).is_err() {
            break;
        }
        if stream.write_all(b"\r\n").is_err() {
            break;
        }
        if stream.flush().is_err() {
            break;
        }
    }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() {
    // Config from env
    let port: u16 = env::var("VIDEO_BRIDGE_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(9090);

    let fps: u32 = env::var("VIDEO_BRIDGE_FPS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(15);

    let quality: i32 = env::var("VIDEO_BRIDGE_QUALITY")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(80);

    let frame_interval = Duration::from_millis(1000 / fps.max(1) as u64);

    // Parse IPC_SUBSCRIBES to discover available camera topics
    let ipc_subscribes: HashMap<String, String> = serde_json::from_str(
        &env::var("IPC_SUBSCRIBES").unwrap_or_else(|_| "{}".into()),
    )
    .expect("[video_bridge] failed to parse IPC_SUBSCRIBES");

    let camera_topics: Vec<String> = ipc_subscribes
        .iter()
        .filter(|(_, type_name)| type_name.as_str() == "CameraFrame")
        .map(|(topic, _)| topic.clone())
        .collect();

    if camera_topics.is_empty() {
        eprintln!("[video_bridge] No CameraFrame topics in IPC_SUBSCRIBES");
        std::process::exit(1);
    }

    println!(
        "[video_bridge] Serving {} topic(s) on port {port}:",
        camera_topics.len()
    );
    for t in &camera_topics {
        println!("  GET /{t}  →  SHM '{t}'");
    }
    println!("[video_bridge] fps={fps}, quality={quality}");

    set_log_level_from_env_or(LogLevel::Warn);

    let addr = format!("0.0.0.0:{port}");
    let listener = TcpListener::bind(&addr).unwrap_or_else(|e| {
        eprintln!("[video_bridge] Failed to bind {addr}: {e}");
        std::process::exit(1);
    });

    println!("[video_bridge] Listening on http://{addr}");

    let shutdown = Arc::new(AtomicBool::new(false));

    for tcp_stream in listener.incoming() {
        let mut tcp_stream = match tcp_stream {
            Ok(s) => s,
            Err(_) => continue,
        };

        if shutdown.load(Ordering::Relaxed) {
            break;
        }

        // Read HTTP request line to get the path
        let mut buf_reader = BufReader::new(tcp_stream.try_clone().unwrap());
        let mut request_line = String::new();
        if buf_reader.read_line(&mut request_line).is_err() {
            continue;
        }

        // Drain remaining headers
        loop {
            let mut line = String::new();
            match buf_reader.read_line(&mut line) {
                Ok(0) | Err(_) => break,
                Ok(_) => {
                    if line == "\r\n" || line == "\n" {
                        break;
                    }
                }
            }
        }

        // Parse "GET /camera/rgb HTTP/1.1"
        let path = request_line
            .split_whitespace()
            .nth(1)
            .unwrap_or("/")
            .trim_start_matches('/')
            .to_string();

        // Find matching camera topic
        let topic = camera_topics.iter().find(|t| t.as_str() == path);

        match topic {
            Some(topic) => {
                // Send MJPEG response headers
                let headers = format!(
                    "HTTP/1.1 200 OK\r\n\
                     Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\
                     Cache-Control: no-cache\r\n\
                     Access-Control-Allow-Origin: *\r\n\
                     Connection: keep-alive\r\n\
                     \r\n"
                );
                if tcp_stream.write_all(headers.as_bytes()).is_err() {
                    continue;
                }

                let _ = tcp_stream.set_nodelay(true);
                let topic = topic.clone();
                let shutdown_clone = Arc::clone(&shutdown);
                println!("[video_bridge] Client connected: /{topic}");

                thread::spawn(move || {
                    stream_mjpeg(&mut tcp_stream, &topic, quality, frame_interval, &shutdown_clone);
                    println!("[video_bridge] Client disconnected: /{topic}");
                });
            }
            None => {
                // Index page
                let body: String = camera_topics
                    .iter()
                    .map(|t| format!("<a href=\"/{t}\">{t}</a><br>"))
                    .collect();
                let html = format!(
                    "<html><body style=\"background:#111;color:#eee;\
                     font-family:monospace;padding:20px\">\
                     <h2>video_bridge</h2>{body}</body></html>"
                );
                let resp = format!(
                    "HTTP/1.1 200 OK\r\n\
                     Content-Type: text/html\r\n\
                     Content-Length: {}\r\n\
                     Access-Control-Allow-Origin: *\r\n\
                     Connection: close\r\n\
                     \r\n\
                     {html}",
                    html.len()
                );
                let _ = tcp_stream.write_all(resp.as_bytes());
            }
        }
    }
}
