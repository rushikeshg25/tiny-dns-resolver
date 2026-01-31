# Tiny DNS Resolver: Technical Deep Dive

This document provides an exhaustive technical specification of the Tiny DNS Resolver implementation, grounded in the standards defined by RFC 1035.

## 1. Project Objective

Tiny DNS Resolver is a low-level implementation of the Domain Name System (DNS) protocol. It bypasses OS-level resolution (getaddrinfo) to interact directly with the global DNS hierarchy using raw UDP packets. The project serves as a reference for binary protocol parsing, recursive state machines, and DNS cache mechanics.

## 2. DNS Packet Layout (Bit-Level)

All DNS packets follow a specific binary layout consisting of a fixed header followed by four variable-length sections.

```text
+---------------------+
|        Header       | (12 bytes)
+---------------------+
|       Question      | (Variable)
+---------------------+
|        Answer       | (Variable)
+---------------------+
|      Authority      | (Variable)
+---------------------+
|      Additional     | (Variable)
+---------------------+
```

### 2.1 The Header Specification

The header is 96 bits (12 bytes) long.

```text
 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                      ID                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    QDCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ANCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    NSCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                    ARCOUNT                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
```

#### Flag Bitfield Analysis

- **QR (1 bit)**: 0 = Query, 1 = Response.
- **Opcode (4 bits)**: Standard query (0), Inverse query (1), Server status (2).
- **AA (1 bit)**: Authoritative Answer. Set if the responding server is the owner of the domain.
- **TC (1 bit)**: Truncated. Set if the packet exceeds 512 bytes (common in UDP).
- **RD (1 bit)**: Recursion Desired. Set by the client if it wants the server to do the work.
- **RA (1 bit)**: Recursion Available. Set by the server if it supports recursive lookups.
- **Z (3 bits)**: Reserved for future use (must be zero).
- **RCODE (4 bits)**: 0 = No error, 1 = Format error, 2 = Server failure, 3 = Name error (NXDOMAIN).

### 2.2 Question Section Format

Each question entry consists of:
1. **QNAME**: Variable length label-sequence encoded as bytes.
2. **QTYPE**: 16-bit code identifying the type of query (A, NS, CNAME, MX, etc.).
3. **QCLASS**: 16-bit code for the class (usually 1 for IN/Internet).

### 2.3 Resource Record (RR) Format

Answers, Authority, and Additional sections are composed of Resource Records:

| Field | Size | Type | Description |
|---|---|---|---|
| NAME | Variable | Labels/Pointer | Domain name matching the question |
| TYPE | 16 bits | Int | RR type code |
| CLASS | 16 bits | Int | RR class code |
| TTL | 32 bits | Int | Seconds the record can be cached |
| RDLENGTH | 16 bits | Int | Length of the RDATA field in bytes |
| RDATA | Variable | Bytes | Type-specific data (e.g., 4 bytes for an IPv4 address) |

## 3. Serialization: The "Labels" format

DNS does not use ASCII dots to separate parts of a domain. It uses a sequence of labels. Each label is prefixed by its length.

**Example: `api.example.org`**

1. Label "api" (length 3): `0x03` + `a` `p` `i`
2. Label "example" (length 7): `0x07` + `e` `x` `a` `m` `p` `l` `e`
3. Label "org" (length 3): `0x03` + `o` `r` `g`
4. Terminator: `0x00`

Final byte sequence: `03 61 70 69 07 65 78 61 6D 70 6C 65 03 6F 72 67 00`

## 4. Deserialization: Pointer Compression (Message Compression)

DNS packets frequently contain repeated domain names (e.g., the name in the Question section usually reappears in the Answer section). To save space, DNS uses a pointer-based compression scheme.

### Mechanism
A domain name entry can be:
1. A sequence of labels (normal).
2. A pointer (2 bytes).
3. A sequence of labels ending with a pointer.

### How to identify a Pointer
If the first two bits of a length byte are `11` (value `0xC0` to `0xFF`), it is a pointer. 

**Format**:
- Bits 0-1: `11` (identifies a pointer).
- Bits 2-15: The offset from the start of the packet where the name is stored.

**Parsing Logic**:
When the `decode_name` function encounters a byte with bits `7` and `6` set:
1. Read the next byte to get the full 14-bit pointer.
2. Store the current stream position.
3. Jump (`seek`) to the pointer offset.
4. Recursively read the name.
5. Jump back and continue.

## 5. Iterative vs Recursive Resolution Logic

The Tiny DNS Resolver implements an **Iterative** approach from the client's perspective, acting as a **Recursive** resolver for the user.

### 5.1 The Resolution Algorithm

The loop in `resolver.py` follows this state machine:

1. **Initialize**: Set `nameserver = "198.41.0.4"` (Initial Root Hint).
2. **Quest**: Send the encoded query to the current `nameserver`.
3. **Parse**: Convert the binary response into a `DNSPacket` object.
4. **Evaluate**:
    - **Step A (Success)**: Does the `Answer` section have an `A` record?
        - Yes: Resolution complete. Return IP.
    - **Step B (Glue)**: Does the `Additional` section have an `A` record for one of the `NS` records in the `Authority` section?
        - Yes: Update `nameserver` to this IP. Repeat from Step 2.
    - **Step C (Referral)**: Does the `Authority` section have an `NS` record?
        - Yes: Resolve the domain of the nameserver first (calling `resolve` recursively). Use that IP as the new `nameserver`. Repeat from Step 2.
    - **Step D (Failure)**: Return "Not found".

### 5.2 Handling "Glue Records"
Glue records are essential when an authoritative nameserver for a domain (`ns1.example.com`) is itself a subdomain of that domain (`example.com`). Without a Glue record (IP address) in the `Additional` section, the resolver would enter an infinite loop trying to resolve the nameserver's address.

## 6. Implementation specifics

- **Socket**: Uses `socket.SOCK_DGRAM` for standard UDP communication on port 53.
- **Timeout**: Hardcoded to 5 seconds to handle packet loss in the unreliable UDP transport.
- **Endianness**: Uses `!` in `struct` formats to enforce Network Byte Order (Big-Endian).

## 7. Folder Structure Analysis

```text
tiny-dns-resolver/
├── src/
│   └── tiny_dns_resolver/
│       ├── packet.py     # Binary bit-manipulation and object mapping
│       ├── resolver.py   # State machine for the resolution loop
│       └── main.py       # Unix-style CLI wrapper
├── tests/
│   └── test_resolver.py  # Integration tests against live root servers
└── Makefile              # Task runner (uv-integrated)
```

## 8. Examples