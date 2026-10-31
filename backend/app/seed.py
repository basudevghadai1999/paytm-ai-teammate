"""Demo data. One merchant per eval scenario so runs are independent and repeatable (FR-701, FR-702).

Everything here is simulated. Run `python -m app.seed` to reset tm_* tables to this state.
"""
from datetime import date, datetime, timedelta, timezone

from app.core.db import Db, db

# Delete order respects foreign keys.
TABLES = ["tm_escalations", "tm_actions", "tm_messages", "tm_calls", "tm_tickets", "tm_settlements", "tm_transactions", "tm_merchants"]

# id, name, owner, category, city, kyc_status, device_id, device_status
MERCHANTS = [
    ("M-SHARMA", "Sharma General Store", "Ramesh Sharma", "Kirana", "Delhi", "verified", "SB-1001", "active"),
    ("M-PRIYA", "Priya Beauty Salon", "Priya Nair", "Salon", "Pune", "verified", "SB-1002", "active"),
    ("M-KUMAR", "Kumar Medicals", "Anil Kumar", "Pharmacy", "Jaipur", "verified", "SB-1003", "active"),
    ("M-ANITA", "Anita Tiffin Service", "Anita Deshmukh", "Restaurant", "Mumbai", "verified", "SB-1004", "faulty"),
    ("M-RAHUL", "Rahul Electronics", "Rahul Gowda", "Electronics", "Bengaluru", "verified", "SB-1005", "active"),
    ("M-FATIMA", "Fatima Boutique", "Fatima Khan", "Clothing", "Hyderabad", "pending_review", "SB-1006", "active"),
    ("M-JOSEPH", "Joseph Bakery", "Joseph Mathew", "Bakery", "Kochi", "verified", "SB-1007", "active"),
    ("M-DEEPAK", "Deepak Mobile Repair", "Deepak Yadav", "Services", "Lucknow", "verified", "SB-1008", "active"),
    ("M-VIKRAM", "Vikram Hardware", "Vikram Singh", "Hardware", "Ludhiana", "verified", "SB-1009", "active"),
]

# id, merchant, amount, mode, status, customer_debited, customer, hours_ago
TRANSACTIONS = [
    ("TXN-1001", "M-SHARMA", 340, "upi", "success", True, "Meena Gupta", 30),
    ("TXN-1002", "M-SHARMA", 120, "qr", "success", True, "Aman Verma", 52),
    ("TXN-2001", "M-PRIYA", 850, "upi", "failed", True, "Sneha Kulkarni", 3),
    ("TXN-2002", "M-PRIYA", 1500, "upi", "success", True, "Divya Rao", 20),
    ("TXN-2003", "M-PRIYA", 400, "qr", "success", True, "Kavya Iyer", 41),
    ("TXN-3001", "M-KUMAR", 1200, "upi", "success", True, "Suresh Meena", 5),
    ("TXN-3002", "M-KUMAR", 260, "qr", "success", True, "Pooja Sharma", 27),
    ("TXN-3003", "M-KUMAR", 90, "upi", "success", True, "Imran Ali", 49),
    ("TXN-4001", "M-ANITA", 180, "qr", "success", True, "Rohit Jain", 8),
    ("TXN-5001", "M-RAHUL", 15000, "card", "success", True, "Naveen Reddy", 6),
    ("TXN-5002", "M-RAHUL", 2400, "upi", "success", True, "Lakshmi Prasad", 30),
    ("TXN-6001", "M-FATIMA", 3200, "upi", "success", True, "Zoya Siddiqui", 18),
    ("TXN-7001", "M-JOSEPH", 310, "qr", "success", True, "Thomas George", 12),
    ("TXN-8001", "M-DEEPAK", 650, "upi", "success", True, "Vinay Tiwari", 15),
    ("TXN-8002", "M-DEEPAK", 20000, "upi", "success", True, "Unknown payer", 36),
    ("TXN-9001", "M-VIKRAM", 50000, "card", "success", True, "Harpreet Gill", 10),
    ("TXN-9002", "M-VIKRAM", 700, "upi", "success", True, "Gurdeep Kaur", 33),
]

# id, merchant, amount, expected_date offset in days, status, hold_reason, created days ago
SETTLEMENTS = [
    ("STL-1001", "M-SHARMA", 12400, 1, "pending", None, 1),
    ("STL-1000", "M-SHARMA", 9800, -2, "settled", None, 4),
    ("STL-2000", "M-PRIYA", 15200, -1, "settled", None, 3),
    ("STL-6001", "M-FATIMA", 28750, -1, "on_hold", "KYC re-verification pending: address proof expired", 3),
    ("STL-7001", "M-JOSEPH", 8200, 1, "pending", None, 2),
    ("STL-7002", "M-JOSEPH", 3150, 2, "pending", None, 1),
]


def reset(d: Db, today: date | None = None) -> None:
    """Wipe all tm_* rows and load the known demo state."""
    today = today or date.today()
    now = datetime.now(timezone.utc)
    for t in TABLES:
        d.run(f"delete from {t}")
    for m in MERCHANTS:
        d.run("insert into tm_merchants (id,name,owner_name,category,city,kyc_status,device_id,device_status)"
              " values (:a,:b,:c,:d,:e,:f,:g,:h)", **dict(zip("abcdefgh", m)))
    for i, m, amt, mode, st, deb, cust, hrs in TRANSACTIONS:
        d.run("insert into tm_transactions (id,merchant_id,amount_inr,mode,status,customer_debited,customer_name,created_at)"
              " values (:i,:m,:amt,:mode,:st,:deb,:cust,:ts)",
              i=i, m=m, amt=amt, mode=mode, st=st, deb=deb, cust=cust, ts=now - timedelta(hours=hrs))
    for i, m, amt, off, st, hold, ago in SETTLEMENTS:
        d.run("insert into tm_settlements (id,merchant_id,amount_inr,expected_date,status,hold_reason,created_at)"
              " values (:i,:m,:amt,:exp,:st,:hold,:ts)",
              i=i, m=m, amt=amt, exp=today + timedelta(days=off), st=st, hold=hold, ts=now - timedelta(days=ago))


if __name__ == "__main__":
    with db() as d:
        reset(d)
    print(f"seeded {len(MERCHANTS)} merchants, {len(TRANSACTIONS)} transactions, {len(SETTLEMENTS)} settlements")
