import os
import re
import sys

FORBIDDEN_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|private[_-]?key)\s*=\s*['\"][A-Za-z0-9+/=]{16,}['\"]", "Hardcoded API/Secret Key"),
    (r"(?i)password\s*=\s*['\"][A-Za-z0-9@#$%^&*!]{6,}['\"]", "Hardcoded plain password (excluding tests/seeds)"),
    (r"DEBUG\s*=\s*True", "DEBUG flag set to True"),
    (r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]", "Wildcard CORS origin allow_origins=['*']"),
    (r"(?i)SELECT\s+.*?\s+FROM\s+.*?\s*['\"]\s*\+\s*", "Potential SQL Injection via string concatenation"),
    (r"(?i)f['\"]SELECT\s+.*?\s+FROM\s+.*?\{", "Potential SQL Injection via f-string interpolation"),
    (r"\beval\(", "Dangerous eval() call"),
    (r"\bexec\(", "Dangerous exec() call"),
    (r"\bos\.system\(", "Dangerous os.system() call"),
    (r"\bsubprocess\.call\([^,]+shell\s*=\s*True", "Dangerous shell=True in subprocess"),
]

EXCLUDED_DIRS = {".git", ".pytest_cache", "node_modules", "dist", "build", "__pycache__"}
EXCLUDED_FILES = {"seed.py", "security_audit.py", "test_security.py", ".env", ".env.example"}

def audit_codebase(root_dir: str):
    issues = []
    print(f"Starting Static Application Security Testing (SAST) on: {root_dir}")
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        
        for fname in filenames:
            if fname in EXCLUDED_FILES:
                continue
            if not (fname.endswith(".py") or fname.endswith(".env") or fname.endswith(".json") or fname.endswith(".js") or fname.endswith(".jsx")):
                continue

            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                lines = content.splitlines()
                for line_no, line in enumerate(lines, 1):
                    for pattern, desc in FORBIDDEN_PATTERNS:
                        # Allow .env.example placeholder
                        if fname == ".env.example" and "insecure-placeholder" in line:
                            continue
                        if re.search(pattern, line):
                            issues.append({
                                "file": fpath,
                                "line": line_no,
                                "desc": desc,
                                "content": line.strip()
                            })
            except Exception as e:
                print(f"Error reading {fpath}: {e}")

    return issues

if __name__ == "__main__":
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    issues = audit_codebase(target)
    if issues:
        print(f"\n[SECURITY AUDIT FAILED] Found {len(issues)} security issue(s):")
        for iss in issues:
            print(f"  - {iss['file']}:{iss['line']} [{iss['desc']}]: {iss['content']}")
        sys.exit(1)
    else:
        print("\n[SECURITY AUDIT PASSED] Zero security violations discovered!")
        sys.exit(0)
