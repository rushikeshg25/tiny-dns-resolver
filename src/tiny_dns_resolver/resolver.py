import socket
import random
from tiny_dns_resolver.packet import (
    DNSHeader, DNSQuestion, DNSPacket, encode_name, 
    TYPE_A, TYPE_NS, CLASS_IN
)

def build_query(domain: str, record_type: int = TYPE_A) -> bytes:
    header = DNSHeader(id=random.randint(0, 65535), flags=0x0100, num_questions=1)
    question = DNSQuestion(name=encode_name(domain), type_=record_type, class_=CLASS_IN)
    return header.to_bytes() + question.to_bytes()

def send_query(query: bytes, server: str, port: int = 53) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    try:
        sock.sendto(query, (server, port))
        data, _ = sock.recvfrom(1024)
        return data
    finally:
        sock.close()

def resolve(domain: str, record_type: int = TYPE_A) -> str:
    # Root servers hints (a.root-servers.net)
    nameserver = "198.41.0.4"
    
    while True:
        print(f"Querying {nameserver} for {domain}...")
        query = build_query(domain, record_type)
        response_data = send_query(query, nameserver)
        packet = DNSPacket.from_bytes(response_data)
        
        # 1. Look for answers
        for record in packet.answers:
            if record.type_ == TYPE_A:
                return socket.inet_ntoa(record.data)
        
        # 2. Look for authority/additionals (Glue records)
        ns_ip = None
        for record in packet.additionals:
            if record.type_ == TYPE_A:
                ns_ip = socket.inet_ntoa(record.data)
                break
        
        if ns_ip:
            nameserver = ns_ip
            continue
            
        # 3. Look for NS records in authority and resolve them
        ns_domain = None
        for record in packet.authorities:
            if record.type_ == TYPE_NS:
                # Need to decode the NS domain string from record.data
                from tiny_dns_resolver.packet import decode_name
                import io
                ns_domain = decode_name(io.BytesIO(record.data)).decode("ascii")
                break
        
        if ns_domain:
            # Recursively resolve the nameserver's own domain
            # (In a real resolver we'd be careful about infinite recursion)
            print(f"Resolving nameserver {ns_domain}...")
            nameserver = resolve(ns_domain)
            continue
            
        return "Not found"
