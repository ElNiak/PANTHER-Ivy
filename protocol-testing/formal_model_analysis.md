# Formal Model Architecture Analysis

## 1. Cross-Protocol Structural Analysis

### Models Examined

| Protocol | Status | Transport | Directory Structure |
|----------|--------|-----------|-------------------|
| **QUIC** | Complete | UDP + TLS 1.3 | 12 subdirectories, 202+ files, ~73MB |
| **BGP** | Partial | TCP | 5 subdirectories, populated stack/utils/entities |
| **CoAP** | Partial | UDP + DTLS | 9 subdirectories, ser/deser empty |
| **MiniP** | Partial | UDP | Flat structure, 1 main directory |
| **System** | Empty | — | 7 subdirectories, all `.gitkeep` |
| **new_prot** | Template | — | 4 subdirectories, all empty files |
| **HTTP** | Placeholder | — | Only `.gitkeep` |

### APT Model (Cross-Cutting)

The APT model in `apt/` spans across protocols with protocol-specific bindings currently implemented for QUIC and MiniP. It models six attack lifecycle stages (Reconnaissance → Infiltration → C2 → Privilege Escalation → Persistence → Exfiltration) plus white noise distraction attacks.

---

## 2. General Template Structure

The analysis reveals **14 structural layers** organized into 4 groups. The diagram (Page 1) uses color coding to distinguish generic infrastructure (blue) from protocol-specific requirement zones (orange), optional layers (green), and APT cross-cutting concerns (purple).

### Core Protocol Stack (Always Required)

1. **Type Definitions** (`{prot}_types.ivy`) — Identifiers, bit vectors, enumerations
2. **Application Layer** (`{prot}_application.ivy`) — Data transfer semantics
3. **Security/Handshake Layer** (`{prot}_security.ivy`) — Key establishment, handshake
4. **Frame/Message Layer** (`{prot}_frame.ivy`) — Protocol data unit definitions
5. **Packet Layer** (`{prot}_packet.ivy`) — Wire-level packet structure
6. **Protection Layer** (`{prot}_protection.ivy`) — Encryption/decryption
7. **Connection/State Management** (`{prot}_connection.ivy`) — Session lifecycle
8. **Transport Parameters** (`{prot}_transport_parameters.ivy`) — Negotiable parameters
9. **Error Handling** (`{prot}_error_code.ivy`) — Error taxonomy

### Entity Model (Always Required)

10. **Entity Definitions** (`ivy_{prot}_{role}.ivy`) — Network participant instances
11. **Entity Behavior** (`ivy_{prot}_{role}_behavior.ivy`) — FSM and constraints
12. **Shims** (`{prot}_shim.ivy`) — Implementation bridge

### Infrastructure (Mostly Reusable)

13. **Serialization/Deserialization** (`{prot}_ser.ivy`, `{prot}_deser.ivy`)
14. **Utilities** (`byte_stream.ivy`, `file.ivy`, `time.ivy`, `random_value.ivy`, `locale.ivy`)

### Optional Layers (Protocol-Dependent)

- **Security Sub-Protocol** (`tls_stack/` or `dtls_stack/`)
- **FSM Modules** (`{prot}_fsm/`)
- **Recovery & Congestion** (`{prot}_recovery/` or `{prot}_congestion/`)
- **Extensions** (`{prot}_extensions/`)
- **Attacks Stack** (`{prot}_attacks_stack/`)
- **Stream/Flow Management** (`{prot}_stream.ivy`)

---

## 3. Protocol-Specific Requirement Locations

Every layer marked orange in the diagram contains protocol-specific requirements. The key insight is that **almost nothing in the core protocol stack is truly generic** — the template provides a structural pattern, but the content of each layer is entirely protocol-dependent. The only genuinely reusable components are:

- `byte_stream.ivy` — identical across protocols
- `file.ivy` — identical across protocols
- `random_value.ivy` — identical across protocols
- The shim *pattern* (not implementation) — same bridge architecture

**Where protocol-specific requirements concentrate most heavily:**

1. **Frame/Message Layer** — This is where the protocol's semantics live. QUIC defines 20+ frame types with complex interactions; BGP has 4 message types with path attribute rules; CoAP has methods + 15 option types.

2. **Entity Behavior** — The behavioral constraints (before/after monitors) encode the RFC requirements. This is the largest and most complex protocol-specific code. QUIC's behavior files are ~15k lines each.

3. **Serialization/Deserialization** — Wire format encoding is entirely protocol-specific. QUIC has ~47k lines across 12+ file pairs; BGP splits by message type.

4. **Connection/State Management** — State machines differ fundamentally: QUIC uses CID-based connection tracking with migration; BGP uses a 6-state FSM (Idle→Established); CoAP uses a token-based request/response matching with observe states.

---

## 4. Template Adaptations for Other Protocol Categories

### Connection-Oriented Transport (SSH, SMTP, FTP, HTTP/1.1)

Replace the UDP datagram layer with TCP stream handling. The packet layer simplifies significantly since TCP handles segmentation and ordering. Recovery/congestion modules are not needed. The shim uses TCP socket APIs. Serialization becomes stream-oriented rather than packet-oriented.

### Publish/Subscribe (MQTT, AMQP, XMPP)

The application layer needs topic and subscription management. A Broker entity is required beyond the standard client/server pair. QoS level handling adds a reliability dimension absent from request/response protocols. Session persistence and will/testament messages create additional state management requirements.

### Routing Protocols (OSPF, IS-IS, RIP)

Require a Routing Information Base (RIB) data structure, neighbor discovery module, route computation algorithms, and convergence timing models. Entities are symmetric (speakers/peers) rather than client/server. The topology/area model adds a dimension not present in point-to-point protocols.

### Real-Time Media (RTP, WebRTC, SIP)

Timing and latency requirements become critical protocol properties. Need jitter buffer modeling, codec negotiation via companion signaling protocols (SDP), and Forward Error Correction rather than retransmission for recovery. The companion control protocol (RTCP) requires a dual-protocol model.

### IoT/Constrained (MQTT-SN, LwM2M, Zigbee)

Resource discovery and proxy/gateway entities are needed. Block-wise transfer and observe patterns add to the application layer. Security is simplified (OSCORE, minimal DTLS). The entity model expands to include constrained endpoints with different capabilities.

### Name Resolution (DNS, mDNS, LDAP)

Stateless or quasi-stateless operation simplifies connection management significantly. Record type definitions replace stream/frame structures. Recursive/iterative resolution models add delegation semantics. DNSSEC adds an optional security extension. No persistent connection state means the FSM layer can be omitted.

### Multiplexed Secure Transport (QUIC, HTTP/2, HTTP/3, SCTP)

This is the most complex category, requiring all optional layers. Full stream management with per-stream FSMs, integrated TLS security stack, connection migration support, multiple encryption levels, and comprehensive recovery/congestion control. QUIC serves as the reference implementation of this category.

### VPN/Tunneling (WireGuard, IPsec/IKEv2, OpenVPN)

Tunnel establishment replaces connection management. Encapsulation/decapsulation is the primary packet-level operation. Key exchange (Diffie-Hellman, Noise protocol) is the security foundation. Security Association management and anti-replay windows are unique requirements. The protection layer becomes the most complex component.

---

## 5. Decision Matrix for Template Selection

| Protocol Property | Template Impact |
|---|---|
| Connection-oriented? | → TCP layer, simplified packet structure |
| Built-in reliability? | → Add recovery/congestion modules |
| Multiplexed streams? | → Add stream management + per-stream FSM |
| Integrated security? | → Add TLS/DTLS stack + protection layer |
| Peer-to-peer? | → Symmetric entities (Speaker/Peer) |
| Pub/Sub pattern? | → Add broker entity + topic/subscription |
| Extension mechanism? | → Add extensions module |
| Stateless? | → Simplify connection/state management |
| Tunneling? | → Add encapsulation + SA management |
| Real-time? | → Add timing constraints + FEC recovery |
