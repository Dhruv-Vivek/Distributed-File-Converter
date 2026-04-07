"""
Distributed File Conversion Service - CLIENT
=============================================
Connects to the server over SSL/TLS, uploads a file,
requests conversion, and downloads the result.

Usage:
  python client.py <file_path> <output_extension>

Examples:
  python client.py report.txt .pdf
  python client.py data.csv .json
  python client.py photo.png .pdf
  python client.py records.json .csv
"""

import socket
import ssl
import os
import sys
import json
import time
import argparse

# ─── Configuration ────────────────────────────────────────────────────────────
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9443
CERT_FILE   = os.path.join(os.path.dirname(__file__), "../certs/server.crt")
BUFFER_SIZE = 4096
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "../downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ─── Socket Helpers ──────────────────────────────────────────────────────────

def recv_all(sock, length):
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(min(BUFFER_SIZE, length - len(buf)))
        if not chunk:
            raise ConnectionError("Connection closed by server")
        buf += chunk
    return buf


def send_json(sock, obj):
    msg = json.dumps(obj).encode("utf-8")
    sock.sendall(len(msg).to_bytes(4, "big") + msg)


def recv_json(sock):
    length = int.from_bytes(recv_all(sock, 4), "big")
    return json.loads(recv_all(sock, length).decode("utf-8"))


# ─── Main Client Logic ────────────────────────────────────────────────────────

def convert_file(file_path, output_ext, verbose=True):
    """
    Upload `file_path` to the conversion server and
    save the converted output. Returns performance dict.
    """
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)

    if not output_ext.startswith("."):
        output_ext = "." + output_ext

    file_size = os.path.getsize(file_path)
    filename  = os.path.basename(file_path)

    # Build SSL context (verify server cert)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(CERT_FILE)
    ctx.check_hostname = False          # Self-signed cert; disable hostname check
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    print(f"\n{'='*55}")
    print(f"  Distributed File Conversion Service - Client")
    print(f"{'='*55}")
    print(f"  File      : {filename} ({file_size:,} bytes)")
    print(f"  Convert to: {output_ext}")
    print(f"  Server    : {SERVER_HOST}:{SERVER_PORT} (TLS)")
    print(f"{'='*55}\n")

    t_connect_start = time.time()

    with socket.create_connection((SERVER_HOST, SERVER_PORT)) as raw_sock:
        with ctx.wrap_socket(raw_sock, server_hostname=SERVER_HOST) as ssl_sock:
            t_connected = time.time()
            if verbose:
                print(f"[✓] TLS handshake complete ({(t_connected - t_connect_start)*1000:.1f} ms)")
                print(f"    Cipher: {ssl_sock.cipher()[0]}")

            # Step 1: Send metadata
            send_json(ssl_sock, {
                "filename":   filename,
                "output_ext": output_ext,
                "file_size":  file_size,
            })

            # Step 2: Wait for ACK, then send file
            ack = recv_json(ssl_sock)
            if not ack.get("ack"):
                print(f"[ERROR] Server did not ACK: {ack}")
                return None

            if verbose:
                print(f"[✓] Server acknowledged. Uploading file...")

            t_upload_start = time.time()
            with open(file_path, "rb") as f:
                ssl_sock.sendall(f.read())
            t_upload_done = time.time()
            upload_time = t_upload_done - t_upload_start

            if verbose:
                throughput = file_size / upload_time / 1024 if upload_time > 0 else 0
                print(f"[✓] Upload complete in {upload_time*1000:.1f} ms ({throughput:.1f} KB/s)")

            # Step 3: Receive job_id
            job_info = recv_json(ssl_sock)
            job_id   = job_info.get("job_id", "unknown")
            if verbose:
                print(f"[✓] Job queued: {job_id}")
                print(f"    Waiting for server to convert...")

            # Step 4: Receive result
            t_wait_start = time.time()
            result = recv_json(ssl_sock)
            t_got_result = time.time()

            if result["status"] == "error":
                print(f"\n[✗] Conversion failed: {result.get('error')}")
                return result

            out_size = result["file_size"]
            out_name = result["output_file"]
            server_elapsed = result.get("elapsed_sec", 0)

            if verbose:
                print(f"[✓] Conversion done (server: {server_elapsed*1000:.1f} ms)")
                print(f"    Downloading result: {out_name} ({out_size:,} bytes)...")

            # Receive file bytes
            t_dl_start = time.time()
            file_data  = recv_all(ssl_sock, out_size)
            t_dl_done  = time.time()
            dl_time    = t_dl_done - t_dl_start

            # Save locally
            save_path = os.path.join(DOWNLOAD_DIR, out_name)
            with open(save_path, "wb") as f:
                f.write(file_data)

            t_total = t_dl_done - t_connect_start
            dl_throughput = out_size / dl_time / 1024 if dl_time > 0 else 0

            print(f"\n{'='*55}")
            print(f"  [✓] SUCCESS")
            print(f"  Output saved : {save_path}")
            print(f"  Output size  : {out_size:,} bytes")
            print(f"  Upload speed : {file_size/upload_time/1024:.1f} KB/s" if upload_time > 0 else "")
            print(f"  Download spd : {dl_throughput:.1f} KB/s")
            print(f"  Server conv. : {server_elapsed*1000:.1f} ms")
            print(f"  Total time   : {t_total*1000:.1f} ms")
            print(f"{'='*55}\n")

            return {
                "status":       "success",
                "job_id":       job_id,
                "output_path":  save_path,
                "input_bytes":  file_size,
                "output_bytes": out_size,
                "upload_ms":    round(upload_time * 1000, 2),
                "server_ms":    round(server_elapsed * 1000, 2),
                "total_ms":     round(t_total * 1000, 2),
            }


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Distributed File Conversion Service - Client"
    )
    parser.add_argument("file", help="Path to the input file")
    parser.add_argument("ext",  help="Desired output extension (e.g. .pdf, .json, .csv)")
    parser.add_argument("--server", default=SERVER_HOST, help="Server hostname/IP")
    parser.add_argument("--port",   default=SERVER_PORT, type=int)
    args = parser.parse_args()

    SERVER_HOST = args.server
    SERVER_PORT = args.port

    convert_file(args.file, args.ext)
