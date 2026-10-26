# NEXUS-OS Network Packet Inspection Guide (Wireshark & HTTP/2 Analysis)

This document provides step-by-step instructions for inspecting cluster IPC and RPC traffic using Wireshark or `tcpdump`, prepared for OSDS Practical 11 and final-year viva defense.

---

## 1. Network Architecture & Protocols

NEXUS-OS supports dual protocol transports across distributed nodes:
1. **TCP-JSON (Legacy IPC & Control Plane)**: Plain newline-delimited JSON over persistent TCP sockets (`port 9000` on Coordinator, ephemeral ports on worker nodes).
2. **gRPC / HTTP/2 (Inter-Node & High-Performance RPC)**: Binary Protocol Buffers framing over HTTP/2 multiplexed streams (`CoordinatorService` and `NodeService`).

---

## 2. Packet Capture Setup

### On Localhost (Development / Test)
1. Open Wireshark.
2. Select the **Npcap Loopback Adapter** (or `Adapter for loopback traffic capture` on Windows / `lo0` on macOS / `lo` on Linux).
3. Start capture.

### On Docker Bridge Network (Phase 9 Cluster)
To capture container-to-container packets on Linux / Docker:
```bash
# Identify the Docker bridge interface
ip addr show | grep docker0
# Or capture directly on the bridge
sudo tcpdump -i docker0 -w logs/nexus_cluster.pcap
```

---

## 3. Wireshark Display Filters

| Inspection Goal | Wireshark Display Filter | What to Observe |
|---|---|---|
| **All Coordinator Traffic** | `tcp.port == 9000` | Full TCP three-way handshake (`SYN`, `SYN-ACK`, `ACK`), keep-alive heartbeats, and payload segments. |
| **TCP-JSON Messages** | `tcp.port == 9000 and data` | Inspect JSON string: `{"type": "HEARTBEAT", "ts": 14, "vc": {...}}`. Notice ASCII overhead and readable field names. |
| **All gRPC / HTTP/2 Calls** | `http2` | HTTP/2 connection preface (`PRI * HTTP/2.0`), SETTINGS frames, WINDOW_UPDATE, HEADERS, and DATA frames. |
| **gRPC Method Filtering** | `http2.header.value contains "nexus.NodeService"` | Specific inter-node RPC invocations (`PutBlock`, `GetBlock`, `RaRequest`). |
| **Ricart-Agrawala Mutual Exclusion** | `http2 contains "RaRequest" or http2 contains "RaReply"` | Timestamp-ordered mutual exclusion request exchanges. |
| **Logical Clock Envelopes** | `json.value or http2.data.data` | Inspect Lamport integer `ts` and Vector Clock map `vc` stamped on every packet. |

---

## 4. Frame Analysis: TCP-JSON vs gRPC HTTP/2

### Frame 1: TCP-JSON Protocol (`port 9000`)
- **Transport**: Raw TCP segment.
- **Payload**: ASCII/UTF-8 JSON string delimited by `\n`.
- **Payload Overhead**: Redundant key strings (`"block_id"`, `"checksum"`, `"content"`), base64 encoding expands binary data by 33%.
- **Stream Semantics**: One request per socket connection or sequential serialized messages over a single TCP stream.

### Frame 2: gRPC HTTP/2 Protocol
- **Transport**: HTTP/2 over TLS or cleartext (`h2c`).
- **Framing**:
  - `HEADERS` frame: HTTP/2 headers with HPACK compression (`:method = POST`, `:path = /nexus.NodeService/PutBlock`, `content-type = application/grpc`).
  - `DATA` frame: 5-byte gRPC prefix (1 compressed flag byte + 4-byte big-endian message length) followed by binary Protobuf bytes.
- **Payload Overhead**: Field numbers (1, 2, 3...) encoded as varints rather than text string keys; raw binary bytes for block data without base64 overhead.
- **Multiplexing**: Multiple concurrent RPCs multiplexed over a single TCP connection across independent stream IDs, eliminating Head-of-Line (HoL) blocking at the application layer.

---

## 5. Viva Defense Screenshots

For course practical documentation, capture the following two screenshots and place them in `docs/screenshots/`:

1. `docs/screenshots/wireshark_tcp_json.png`:
   - Filter: `tcp.port == 9000`
   - Highlight: Follow TCP Stream showing JSON payload with `type`, `ts`, and `vc`.

2. `docs/screenshots/wireshark_grpc_http2.png`:
   - Filter: `http2`
   - Highlight: Dissected HTTP/2 HEADERS frame showing `:path: /nexus.NodeService/PutBlock` and subsequent DATA frame containing Protobuf varints.
