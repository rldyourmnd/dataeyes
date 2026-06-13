"""
Buggy Python service fixture for ultra_code_review benchmark task.

This is a deliberately broken FastAPI-style microservice with 15 intentional bugs
of varying severity (security, logic, performance, concurrency).

Models must identify ALL bugs, classify them, and provide fixed versions.
"""

# ─── BUGGY CODE BEGIN ───────────────────────────────────────────────────────
BUGGY_SERVICE_CODE = '''
"""
UserService: REST API service for user management and billing.
Handles authentication, subscription pricing, and usage tracking.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import sqlite3
import time
from datetime import datetime
from typing import Any

# BUG #1: Hardcoded secret key – must never appear in source
SECRET_KEY = "super-secret-key-do-not-share-abc123"
ADMIN_TOKEN = "admin-override-token-xyz"

# BUG #2: Module-level mutable state with no bound – memory leak
_request_log: list[dict] = []

# BUG #3: Non-cryptographic PRNG used for security-sensitive token
def generate_session_token(user_id: int) -> str:
    random.seed(user_id)          # seeded with predictable value
    return hex(random.getrandbits(128))[2:]

# ── Authentication ────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()   # BUG #4: MD5 for passwords

def verify_password(plain: str, hashed: str) -> bool:
    # BUG #5: Non-constant-time comparison leaks timing information
    return hash_password(plain) == hashed

def check_admin_token(token: str) -> bool:
    # BUG #6: Backdoor – any request with ADMIN_TOKEN bypasses auth entirely
    if token == ADMIN_TOKEN:
        return True
    return token == SECRET_KEY

# ── Database helpers ──────────────────────────────────────────────────────────

_DB_PATH = "users.db"

def get_db():
    return sqlite3.connect(_DB_PATH)

def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    # BUG #7: String interpolation → SQL injection
    cursor = conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2],
            "tier": row[3], "usage_gb": row[4], "created_at": row[5]}

def get_user_by_email(email: str) -> dict | None:
    conn = get_db()
    # BUG #7 (same): SQL injection via email field
    cursor = conn.execute(f"SELECT * FROM users WHERE email = \'{email}\'")
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2],
            "tier": row[3], "usage_gb": row[4], "created_at": row[5]}

def list_users_in_org(org_id: int) -> list[dict]:
    conn = get_db()
    cursor = conn.execute(
        "SELECT id, email, tier FROM users WHERE org_id = ?", (org_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1], "tier": r[2]} for r in rows]

# ── Pricing & Billing ─────────────────────────────────────────────────────────

TIER_PRICES = {
    "starter":    9.99,
    "pro":       29.99,
    "business":  99.99,
    "enterprise": 299.99,
}

TIER_LIMITS_GB = {
    "starter":    10,
    "pro":        100,
    "business":   1000,
    "enterprise": float("inf"),
}

def calculate_monthly_bill(user: dict) -> float:
    tier = user.get("tier", "starter")
    base = TIER_PRICES.get(tier, 9.99)
    usage_gb = float(user.get("usage_gb", 0))
    limit_gb = TIER_LIMITS_GB.get(tier, 10)

    # BUG #8: Overage check uses wrong comparison (< instead of >)
    # Users who EXCEED their limit are charged base price, not overage
    if usage_gb < limit_gb:
        overage_gb = usage_gb - limit_gb
        overage_charge = overage_gb * 0.10
        return round(base + overage_charge, 2)
    return round(base, 2)

def apply_discount(price: float, discount_pct: int) -> float:
    # BUG #9: discount_pct is 0-100 but code treats it as 0.0-1.0
    # e.g. discount_pct=20 → multiplies by 0.8 only if treated as fraction
    # With integer 20: price * (1 - 20) = price * -19  ← massively wrong
    return price * (1 - discount_pct)

def get_invoice_total(user_id: int, discount_pct: int = 0) -> float:
    user = get_user_by_id(user_id)
    if user is None:
        return 0.0
    bill = calculate_monthly_bill(user)
    if discount_pct > 0:
        bill = apply_discount(bill, discount_pct)
    return bill

# ── Usage Tracking ────────────────────────────────────────────────────────────

_usage_counters: dict[int, int] = {}   # user_id → request count

def increment_usage(user_id: int) -> int:
    # BUG #10: Race condition – read-modify-write without lock
    current = _usage_counters.get(user_id, 0)
    time.sleep(0)   # simulates context switch opportunity
    _usage_counters[user_id] = current + 1
    return _usage_counters[user_id]

def record_request(user_id: int, endpoint: str, status_code: int) -> None:
    # BUG #2 (continued): appends forever, never pruned
    _request_log.append({
        "user_id": user_id,
        "endpoint": endpoint,
        "status": status_code,
        "ts": time.time(),
    })

def get_request_count(user_id: int) -> int:
    return sum(1 for r in _request_log if r["user_id"] == user_id)  # O(n) every call

# ── Email Validation ──────────────────────────────────────────────────────────

# BUG #11: Regex accepts invalid emails (e.g. "a@b" with no TLD is matched)
# and rejects valid ones with subdomains (e.g. "user@mail.company.co.uk")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z]{2,4}$")

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))

# ── Date / Expiry Logic ───────────────────────────────────────────────────────

def is_subscription_expired(user: dict) -> bool:
    created_at_str = user.get("created_at", "")
    try:
        # BUG #12: datetime.fromisoformat doesn't handle timezone-aware strings
        # in Python 3.6; and this discards timezone, comparing naive to naive
        # → subscriptions in UTC+X appear expired earlier than they are
        created_at = datetime.fromisoformat(created_at_str)
    except ValueError:
        return True   # treat unparseable as expired
    # 30-day trial
    delta = datetime.now() - created_at   # BUG #12 continued: naive vs aware
    return delta.days > 30

# ── File Export ───────────────────────────────────────────────────────────────

ALLOWED_EXPORT_DIRS = ["/tmp/exports", "/var/data/exports"]

def export_user_data(user_id: int, export_dir: str) -> str:
    # BUG #13: Path traversal – export_dir is not validated against allowlist
    # Attacker passes export_dir="../../etc" to write anywhere
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found")
    path = os.path.join(export_dir, f"user_{user_id}.json")
    with open(path, "w") as f:
        # BUG #14: Writes password_hash to export file (sensitive data leak)
        json.dump(user, f)
    return path

# ── Search & Pagination ───────────────────────────────────────────────────────

def search_users(query: str, page: int = 1, page_size: int = 20) -> list[dict]:
    conn = get_db()
    offset = (page - 1) * page_size
    # BUG #7 (again): SQL injection in search query
    cursor = conn.execute(
        f"SELECT id, email, tier FROM users WHERE email LIKE \'%{query}%\' "
        f"LIMIT {page_size} OFFSET {offset}"
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1], "tier": r[2]} for r in rows]

def paginate(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    # BUG #15: Off-by-one – end index is exclusive so this is actually correct,
    # but the function silently returns empty list when page is 0 or negative
    # instead of raising ValueError. page=0 → start=-20 → items[-20:0] = []
    end = start + page_size
    return items[start:end]

# ── Reporting ─────────────────────────────────────────────────────────────────

def generate_usage_report(org_id: int) -> dict:
    users = list_users_in_org(org_id)
    total_bill = 0.0
    tier_counts: dict[str, int] = {}
    for user in users:
        # BUG #10 (N+1): fetches full user record per user when we already have tier
        full_user = get_user_by_id(user["id"])
        if full_user:
            total_bill += calculate_monthly_bill(full_user)
            t = full_user.get("tier", "starter")
            tier_counts[t] = tier_counts.get(t, 0) + 1
    return {
        "org_id": org_id,
        "user_count": len(users),
        "total_monthly_bill": round(total_bill, 2),
        "tier_distribution": tier_counts,
        "report_generated_at": datetime.now().isoformat(),
    }

def get_top_users_by_usage(limit: int = 10) -> list[dict]:
    # Bubble sort on potentially large list – O(n²)
    # BUG #16: Inefficient algorithm; should use sorted() + key
    log_copy = list(_request_log)
    n = len(log_copy)
    for i in range(n):
        for j in range(0, n - i - 1):
            if log_copy[j]["user_id"] > log_copy[j + 1]["user_id"]:
                log_copy[j], log_copy[j + 1] = log_copy[j + 1], log_copy[j]
    # Deduplicate and take top N
    seen: set[int] = set()
    result = []
    for entry in log_copy:
        uid = entry["user_id"]
        if uid not in seen:
            seen.add(uid)
            result.append({"user_id": uid, "requests": get_request_count(uid)})
    return result[:limit]

# ── Redirect / OAuth helper ───────────────────────────────────────────────────

def build_redirect_url(base_url: str, next_param: str) -> str:
    # BUG #17: Open redirect – next_param is not validated
    # Allows: build_redirect_url("https://app.example.com", "https://evil.com")
    return f"{base_url}?next={next_param}"

# ── Config loader ─────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        # BUG #18: yaml.load without Loader= is dangerous if config has Python objects
        # (using json.load here but same pattern as unsafe yaml.load)
        return json.load(f)

# ── Cache (simple in-memory) ──────────────────────────────────────────────────

_cache: dict[str, tuple[Any, float]] = {}
CACHE_TTL = 300  # seconds

def cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    # BUG #19: Uses system time without monotonic clock – vulnerable to clock skew
    # Also, expired entries accumulate forever (no eviction)
    if time.time() > expires_at:
        return None
    return value

def cache_set(key: str, value: Any) -> None:
    # BUG #20: Cache has no size limit; unbounded growth under heavy load
    _cache[key] = (value, time.time() + CACHE_TTL)

# ── Startup check ─────────────────────────────────────────────────────────────

def check_database_schema() -> bool:
    conn = get_db()
    try:
        conn.execute("SELECT COUNT(*) FROM users")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if check_database_schema():
        logging.info("DB schema OK")
    else:
        logging.error("DB schema missing")
'''

# The 20 planted bugs summarized (for scoring reference):
# BUG_MANIFEST = {
#   1: ("hardcoded_secret",      "critical",  "SECRET_KEY and ADMIN_TOKEN hardcoded in source"),
#   2: ("memory_leak",           "high",      "_request_log grows without bound"),
#   3: ("weak_prng",             "critical",  "random.seed(user_id) – predictable tokens"),
#   4: ("weak_hash",             "critical",  "MD5 used for password hashing"),
#   5: ("timing_attack",         "high",      "Non-constant-time password comparison"),
#   6: ("backdoor",              "critical",  "ADMIN_TOKEN bypasses all auth"),
#   7: ("sql_injection",         "critical",  "f-string interpolation in SQL queries"),
#   8: ("logic_inversion",       "high",      "< instead of > in overage check"),
#   9: ("type_confusion",        "high",      "discount_pct int treated as float fraction"),
#  10: ("race_condition",        "high",      "unsynchronised read-modify-write counter"),
#  11: ("regex_too_permissive",  "medium",    "Email regex accepts no-TLD addresses"),
#  12: ("timezone_naive",        "medium",    "datetime.now() vs tz-aware fromisoformat"),
#  13: ("path_traversal",        "critical",  "export_dir not validated → write anywhere"),
#  14: ("sensitive_data_leak",   "high",      "password_hash included in export JSON"),
#  15: ("off_by_one",            "medium",    "page=0 silently returns empty list"),
#  16: ("inefficient_algorithm", "low",       "O(n²) bubble sort on large list"),
#  17: ("open_redirect",         "high",      "next_param not validated → redirect to evil.com"),
#  18: ("unsafe_deserialisation","medium",    "unsafe load pattern (yaml.load without Loader)"),
#  19: ("monotonic_clock",       "low",       "time.time() not monotonic, entries not evicted"),
#  20: ("unbounded_cache",       "medium",    "Cache grows forever under heavy load"),
# }
