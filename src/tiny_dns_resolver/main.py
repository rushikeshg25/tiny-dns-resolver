import sys
from tiny_dns_resolver.resolver import resolve

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m tiny_dns_resolver.main <domain>")
        sys.exit(1)
    
    domain = sys.argv[1]
    print(f"Resolving {domain}...")
    ip = resolve(domain)
    print(f"IP: {ip}")

if __name__ == "__main__":
    main()
