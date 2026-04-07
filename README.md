# 🚀 Distributed File Conversion Service (TCP + SSL/TLS)

## 📌 Overview

This project implements a **Distributed File Conversion Service** using **Python sockets (TCP)** with **SSL/TLS encryption**.
It follows a **client-server architecture** where clients securely upload files to a server for conversion.

---

## 🧠 Architecture

```
+-------------+        TLS (Secure TCP)        +-------------+
|   Client    |  <---------------------------> |   Server    |
|-------------|                                |-------------|
| Upload File |                                | Accept Conn |
| Request Conv|                                | Queue Jobs  |
| Receive File|                                | Process File|
+-------------+                                +-------------+
                                                      |
                                                      v
                                             +----------------+
                                             | Conversion Core|
                                             +----------------+
```

---

## ⚙️ Features

### 🔐 Secure Communication

* SSL/TLS encryption using Python `ssl` module
* Prevents eavesdropping and tampering

### 📁 File Conversion

Supports multiple conversions:

* `.txt → .pdf`
* `.csv → .json`
* `.image → .pdf`

### ⚡ Concurrent Clients

* Multi-threaded server
* Handles multiple client requests simultaneously

### 📊 Performance Analysis

* Measures:

  * Latency vs file size
  * Throughput
  * Server processing time
* Includes benchmarking scripts

---

## 📂 Project Structure

```
Distributed-File-Converter/
├── server/
│   └── server.py
├── client/
│   └── client.py
├── utils/
│   ├── performance_analysis.py
│   ├── plot_performance.py
│   └── plot_my_conversions.py
├── certs/
│   └── server.crt
├── perf_test_files/
├── generate_certs.py
├── README.md
└── requirements.txt
```

---

## 🚀 Setup Instructions

### 1️⃣ Clone Repository

```
git clone https://github.com/Dhruv-Vivek/Distributed-File-Converter.git
cd Distributed-File-Converter
```

---

### 2️⃣ Install Dependencies

```
pip install -r requirements.txt
```

---

### 3️⃣ Generate SSL Certificates (if needed)

```
python generate_certs.py
```

---

### 4️⃣ Start Server

```
python server/server.py
```

---

### 5️⃣ Run Client

```
python client/client.py input.txt .pdf
```

---

## 🔄 Protocol Design

1. Client connects using TLS
2. Sends:

   * Filename
   * Target format
   * File size
3. Server:

   * Queues job
   * Converts file
   * Sends back result
4. Client saves converted file

---

## 📊 Performance Evaluation

Run:

```
python utils/performance_analysis.py
```

Test files:

* Located in `perf_test_files/`
* Includes multiple sizes (1KB → 250KB, CSV rows)

Metrics analyzed:

* Execution time vs file size
* Server response time
* Concurrent request handling

---

## ⚙️ Design Decisions

* Used **raw TCP sockets** (not HTTP frameworks) to meet assignment requirements
* Implemented **threading** for concurrency
* Used **SSL wrapper** for secure communication
* Modular design (`server`, `client`, `utils`)

---

## 🛠️ Error Handling

* Handles:

  * Invalid file formats
  * Broken connections
  * SSL handshake failures
  * Partial file transfers

---

## 🔐 Security Notes

* TLS ensures encrypted communication
* Private key (`.key`) is not shared publicly
* Certificates stored in `certs/`

---

## 🎯 Conclusion

This project demonstrates:

* Socket programming
* Secure communication (TLS)
* Distributed system design
* Performance evaluation

---
