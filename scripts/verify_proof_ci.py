#!/usr/bin/env python3
"""
FLOP Technocore Contribution Proof CI/CD Verifier
Validates proof JSON schema, Ed25519 signature integrity, and Git HEAD alignment.
Author: Technocore CI Guardians
License: MIT
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add fallback path for technocore_agent
CURRENT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(CURRENT_DIR.parent))

try:
    import technocore_agent
except ImportError:
    # If not present, download official agent script dynamically in CI
    print("Fetching technocore_agent.py from official upstream...")
    import urllib.request
    url = "https://raw.githubusercontent.com/flop-labs/technocore-chat/main/scripts/technocore_agent.py"
    urllib.request.urlretrieve(url, CURRENT_DIR / "technocore_agent.py")
    import technocore_agent

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def get_git_head_commit() -> str | None:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return None

def verify_proof_file(proof_path: Path, strict_head: bool = False) -> bool:
    print(f"\n{BOLD}🔍 Auditing Technocore Contribution Proof: {proof_path}{RESET}")
    print("=" * 60)
    
    if not proof_path.exists():
        print(f"{RED}❌ Error: Proof file not found at {proof_path}{RESET}")
        return False
        
    try:
        data = json.loads(proof_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{RED}❌ Error: Failed to parse JSON: {e}{RESET}")
        return False
        
    # 1. Cryptographic validation
    try:
        technocore_agent.verify_contribution_proof(data)
        print(f"{GREEN}✔ Cryptographic Ed25519 Signature: VALID{RESET}")
        print(f"  • Signer DID:    {YELLOW}{data.get('did')}{RESET}")
        print(f"  • Artifact URL:  {data.get('artifact_url')}")
        print(f"  • Target Commit: {data.get('commit')}")
    except Exception as e:
        print(f"{RED}❌ Cryptographic Signature Verification FAILED: {e}{RESET}")
        return False

    # 2. Strict Git HEAD check if enabled
    if strict_head:
        head = get_git_head_commit()
        if not head:
            print(f"{RED}❌ Error: Cannot determine current Git HEAD in strict mode.{RESET}")
            return False
        target = data.get("commit", "").lower()
        if head.lower() != target:
            print(f"{RED}❌ Error: Proof commit ({target}) does not match current HEAD ({head}).{RESET}")
            return False
        else:
            print(f"{GREEN}✔ Git HEAD Alignment: PERFECT MATCH ({head[:8]}){RESET}")

    print("=" * 60)
    print(f"{GREEN}🎉 All Technocore Proof checks PASSED successfully!{RESET}\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="Technocore Contribution Proof CI Verifier")
    parser.add_argument("proof_file", nargs="?", default="proof/contribution-proof.json", help="Path to proof JSON")
    parser.add_argument("--strict-head", action="store_true", help="Enforce exact match with current git HEAD")
    args = parser.parse_args()
    
    ok = verify_proof_file(Path(args.proof_file), strict_head=args.strict_head)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
