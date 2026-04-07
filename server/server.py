"""
Distributed File Conversion Service - SERVER
=============================================
Handles multiple concurrent clients over SSL/TLS TCP sockets.
Supports: txt->pdf, csv->json, jpg/png->pdf, json->csv
Features: Job queue, concurrent threading, performance logging
"""

import socket
import ssl
import threading
import os
import time
import json
import csv
import queue
import logging
from datetime import datetime
from io import StringIO
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ─── Optional imports ────────────────────────────────────────────────────────
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ─── Configuration ────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 9443
CERT_FILE = os.path.join(os.path.dirname(__file__), "../certs/server.crt")
KEY_FILE  = os.path.join(os.path.dirname(__file__), "../certs/server.key")
UPLOAD_DIR    = os.path.join(os.path.dirname(__file__), "../uploads")
OUTPUT_DIR    = os.path.join(os.path.dirname(__file__), "../converted_output")
PERF_LOG_FILE = os.path.join(os.path.dirname(__file__), "../performance_log.csv")
MAX_WORKERS   = 5           # Max concurrent conversion threads
BUFFER_SIZE   = 4096        # Socket read buffer

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "../server.log"))
    ]
)
log = logging.getLogger("FileConvServer")

# ─── Job Queue & Scheduler ────────────────────────────────────────────────────
job_queue   = queue.Queue()
job_results = {}           # job_id -> result dict
job_lock    = threading.Lock()

def generate_job_id():
    return f"JOB-{int(time.time()*1000)}-{threading.get_ident() % 10000}"

# ─── Conversion Functions ─────────────────────────────────────────────────────

def convert_txt_to_pdf(src_path, dst_path):
    """Plain text -> PDF using fpdf2 (Windows UTF-16 BOM safe)"""
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 not installed. Run: pip install fpdf2")

    # Detect encoding - PowerShell echo saves UTF-16-LE with BOM
    with open(src_path, "rb") as f:
        raw = f.read(4)
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        enc = "utf-16"
    elif raw[:3] == b'\xef\xbb\xbf':
        enc = "utf-8-sig"
    else:
        enc = "utf-8"

    pdf = FPDF()
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()
    pdf.set_font("Courier", size=11)
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin
    with open(src_path, "r", encoding=enc, errors="replace") as f:
        for line in f:
            clean = line.rstrip().encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(effective_width, 7, clean or " ")
    pdf.output(dst_path)


def convert_csv_to_json(src_path, dst_path):
    """CSV -> JSON array"""
    rows = []
    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def convert_json_to_csv(src_path, dst_path):
    """JSON array -> CSV"""
    with open(src_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("JSON must be a non-empty array of objects")
    fieldnames = list(data[0].keys())
    with open(dst_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def convert_image_to_pdf(src_path, dst_path):
    """JPG/PNG -> PDF using Pillow"""
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    img = Image.open(src_path).convert("RGB")
    img.save(dst_path, "PDF", resolution=100.0)
    
def convert_docx_to_pdf(src_path, dst_path):
    """DOCX -> PDF using python-docx + fpdf2"""
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx not installed. Run: pip install python-docx")
    if not FPDF_AVAILABLE:
        raise RuntimeError("fpdf2 not installed.")
    
    doc = Document(src_path)
    pdf = FPDF()
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()
    pdf.set_font("Courier", size=11)
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    for para in doc.paragraphs:
        text = para.text.strip()
        # Heading style — make it bold and bigger
        if para.style.name.startswith("Heading"):
            pdf.set_font("Courier", style="B", size=13)
            clean = text.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(effective_width, 9, clean or " ")
            pdf.set_font("Courier", size=11)
        else:
            clean = text.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(effective_width, 7, clean or " ")

    pdf.output(dst_path)


def dispatch_conversion(src_path, output_ext):
    """Route to the correct converter based on input/output extensions."""
    src_ext = os.path.splitext(src_path)[1].lower()
    base     = os.path.splitext(os.path.basename(src_path))[0]
    dst_name = f"{base}_converted{output_ext}"
    dst_path = os.path.join(OUTPUT_DIR, dst_name)

    converters = {
        (".txt",  ".pdf"): convert_txt_to_pdf,
        (".csv",  ".json"): convert_csv_to_json,
        (".json", ".csv"): convert_json_to_csv,
        (".jpg",  ".pdf"): convert_image_to_pdf,
        (".jpeg", ".pdf"): convert_image_to_pdf,
        (".png",  ".pdf"): convert_image_to_pdf,
        (".docx", ".pdf"): convert_docx_to_pdf,
    }

    key = (src_ext, output_ext)
    if key not in converters:
        raise ValueError(f"Unsupported conversion: {src_ext} -> {output_ext}")

    converters[key](src_path, dst_path)
    return dst_path

# ─── Job Worker Thread ─────────────────────────────────────────────────────────

def job_worker():
    """Worker thread that pulls jobs from the queue and converts files."""
    while True:
        job = job_queue.get()
        if job is None:
            break  # Poison pill to stop worker
        job_id    = job["job_id"]
        src_path  = job["src_path"]
        out_ext   = job["output_ext"]
        client_cb = job["callback"]   # function(result_dict)

        log.info(f"[{job_id}] Starting conversion: {os.path.basename(src_path)} -> {out_ext}")
        start = time.time()

        try:
            dst_path = dispatch_conversion(src_path, out_ext)
            elapsed  = time.time() - start
            file_size = os.path.getsize(src_path)
            result = {
                "status": "success",
                "job_id": job_id,
                "output_file": os.path.basename(dst_path),
                "output_path": dst_path,
                "elapsed_sec": round(elapsed, 4),
                "input_size_bytes": file_size,
            }
            log_performance(job_id, os.path.basename(src_path), out_ext, file_size, elapsed, "success")
            log.info(f"[{job_id}] Done in {elapsed:.3f}s -> {os.path.basename(dst_path)}")
        except Exception as e:
            elapsed = time.time() - start
            result = {"status": "error", "job_id": job_id, "error": str(e)}
            log_performance(job_id, os.path.basename(src_path), out_ext, 0, elapsed, f"error: {e}")
            log.error(f"[{job_id}] Conversion failed: {e}")

        with job_lock:
            job_results[job_id] = result
        client_cb(result)
        job_queue.task_done()


def log_performance(job_id, filename, out_ext, size_bytes, elapsed, status):
    """Append performance data to CSV log."""
    write_header = not os.path.exists(PERF_LOG_FILE)
    with open(PERF_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "job_id", "filename", "output_ext",
                              "input_size_bytes", "elapsed_sec", "status"])
        writer.writerow([datetime.now().isoformat(), job_id, filename,
                         out_ext, size_bytes, round(elapsed, 4), status])

# ─── Client Handler ────────────────────────────────────────────────────────────

def recv_all(sock, length):
    """Receive exactly `length` bytes from socket."""
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(min(BUFFER_SIZE, length - len(buf)))
        if not chunk:
            raise ConnectionError("Client disconnected mid-transfer")
        buf += chunk
    return buf


def send_json(sock, obj):
    msg = json.dumps(obj).encode("utf-8")
    sock.sendall(len(msg).to_bytes(4, "big") + msg)


def recv_json(sock):
    length = int.from_bytes(recv_all(sock, 4), "big")
    return json.loads(recv_all(sock, length).decode("utf-8"))


def handle_client(ssl_sock, addr):
    """
    Protocol:
      1. Client sends JSON metadata: {filename, output_ext, file_size}
      2. Server ACKs, then receives raw file bytes
      3. Server queues job, sends back job_id
      4. After conversion, server sends result JSON + file bytes
    """
    log.info(f"[+] Client connected: {addr}")
    try:
        # Step 1: Receive metadata
        meta = recv_json(ssl_sock)
        filename   = os.path.basename(meta["filename"])   # Sanitize path
        output_ext = meta["output_ext"]
        file_size  = int(meta["file_size"])

        if not output_ext.startswith("."):
            output_ext = "." + output_ext

        log.info(f"    File: {filename} ({file_size} bytes) -> {output_ext}")

        # Step 2: ACK and receive file
        send_json(ssl_sock, {"ack": True, "message": "Ready to receive"})
        file_data = recv_all(ssl_sock, file_size)

        # Save uploaded file
        ts = int(time.time() * 1000)
        saved_name = f"{ts}_{filename}"
        src_path   = os.path.join(UPLOAD_DIR, saved_name)
        with open(src_path, "wb") as f:
            f.write(file_data)
        log.info(f"    Saved upload: {saved_name}")

        # Step 3: Queue job and send job_id
        job_id = generate_job_id()
        result_event = threading.Event()
        result_holder = {}

        def on_done(result):
            result_holder.update(result)
            result_event.set()

        job_queue.put({
            "job_id": job_id,
            "src_path": src_path,
            "output_ext": output_ext,
            "callback": on_done,
        })
        send_json(ssl_sock, {"job_id": job_id, "status": "queued"})

        # Step 4: Wait for result and send back
        result_event.wait(timeout=120)
        if not result_holder:
            send_json(ssl_sock, {"status": "error", "error": "Timeout"})
            return

        if result_holder["status"] == "error":
            send_json(ssl_sock, result_holder)
            return

        # Send result metadata + converted file bytes
        out_path = result_holder["output_path"]
        with open(out_path, "rb") as f:
            out_data = f.read()

        result_holder["file_size"] = len(out_data)
        send_json(ssl_sock, result_holder)
        ssl_sock.sendall(out_data)
        log.info(f"    Sent converted file ({len(out_data)} bytes) to {addr}")

    except (ConnectionError, ConnectionResetError) as e:
        log.warning(f"[!] Client {addr} disconnected: {e}")
    except ssl.SSLError as e:
        log.error(f"[!] SSL error with {addr}: {e}")
    except Exception as e:
        log.error(f"[!] Unexpected error with {addr}: {e}", exc_info=True)
        try:
            send_json(ssl_sock, {"status": "error", "error": str(e)})
        except:
            pass
    finally:
        try:
            ssl_sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        ssl_sock.close()
        log.info(f"[-] Client disconnected: {addr}")

# ─── Server Main ──────────────────────────────────────────────────────────────

def start_server():
    # Start worker thread pool
    workers = []
    for _ in range(MAX_WORKERS):
        t = threading.Thread(target=job_worker, daemon=True)
        t.start()
        workers.append(t)
    log.info(f"Job scheduler started with {MAX_WORKERS} worker threads")

    # Create SSL context
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_sock.bind((HOST, PORT))
    raw_sock.listen(20)

    log.info(f"Server listening on {HOST}:{PORT} (TLS enabled)")
    log.info("Supported conversions: txt->pdf, csv->json, json->csv, jpg/png->pdf")

    try:
        while True:
            conn, addr = raw_sock.accept()
            try:
                ssl_conn = ctx.wrap_socket(conn, server_side=True)
            except ssl.SSLError as e:
                log.warning(f"SSL handshake failed from {addr}: {e}")
                conn.close()
                continue

            thread = threading.Thread(
                target=handle_client,
                args=(ssl_conn, addr),
                daemon=True
            )
            thread.start()
            log.info(f"Active client threads: {threading.active_count() - 1 - MAX_WORKERS}")

    except KeyboardInterrupt:
        log.info("Server shutting down...")
    finally:
        raw_sock.close()
        # Stop workers
        for _ in workers:
            job_queue.put(None)


if __name__ == "__main__":
    start_server()
