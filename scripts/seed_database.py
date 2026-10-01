#!/usr/bin/env python
"""
PolicyPilot — Database Seeder
Creates the admin user and seeds initial document records.

Usage:
    python scripts/seed_database.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import configure_logging, get_logger, get_settings
from backend.auth import hash_password
from backend.database import get_db, User, Document, DocumentVersion

settings = get_settings()
configure_logging()
logger = get_logger("seed_script")

# PW Policy document registry
INITIAL_DOCUMENTS = [
    {"name": "Anti Money Laundering (AML) Policy", "slug": "aml-policy", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Anti-Corruption Policy", "slug": "anti-corruption-policy", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Asset Allocation Policy", "slug": "asset-allocation-policy", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Attendance and Shift Policy", "slug": "attendance-shift-policy", "category": "HR", "department": "Human Resources"},
    {"name": "Code of Business Conduct Policy", "slug": "code-of-business-conduct", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Code of Conduct and Social Media Policy", "slug": "code-of-conduct-social-media", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Comp Off and Extra Pay Policy", "slug": "comp-off-extra-pay", "category": "HR", "department": "Human Resources"},
    {"name": "Conflict of Interest Policy", "slug": "conflict-of-interest", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Equal Opportunity Policy", "slug": "equal-opportunity", "category": "HR", "department": "Human Resources"},
    {"name": "GPA Policy", "slug": "gpa-policy", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Group Medical Coverage Policy", "slug": "group-medical-coverage", "category": "Benefits", "department": "Human Resources"},
    {"name": "GTLI Policy", "slug": "gtli-policy", "category": "Benefits", "department": "Human Resources"},
    {"name": "IJDP Policy", "slug": "ijdp-policy", "category": "HR", "department": "Human Resources"},
    {"name": "International Travel Expense and Reimbursement Policy", "slug": "intl-travel-expense", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Internet Reimbursement Policy", "slug": "internet-reimbursement", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "IT Policies", "slug": "it-policies", "category": "IT", "department": "Information Technology"},
    {"name": "Leave Policy 2026", "slug": "leave-policy-2026", "category": "HR", "department": "Human Resources"},
    {"name": "No Gifts Policy", "slug": "no-gifts-policy", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Outbound Emails Sending Approval Policy", "slug": "outbound-emails-approval", "category": "IT", "department": "Information Technology"},
    {"name": "PIP Policy", "slug": "pip-policy", "category": "HR", "department": "Human Resources"},
    {"name": "POSH Policy", "slug": "posh-policy", "category": "HR", "department": "Human Resources"},
    {"name": "Probation and Confirmation Policy", "slug": "probation-confirmation", "category": "HR", "department": "Human Resources"},
    {"name": "PW Pathshala Discounted Admission Policy", "slug": "pw-pathshala-admission", "category": "Benefits", "department": "Human Resources"},
    {"name": "Acceptable Usage Policy (ISMS)", "slug": "acceptable-usage-isms", "category": "IT", "department": "Information Technology"},
    {"name": "Vibe Coding and Deployment Policy", "slug": "vibe-coding-deployment", "category": "IT", "department": "Information Technology"},
    {"name": "Territorial Army Support Policy", "slug": "territorial-army-support", "category": "HR", "department": "Human Resources"},
    {"name": "Policy on Relatives Working in PW", "slug": "relatives-working-pw", "category": "HR", "department": "Human Resources"},
    {"name": "Reassociation Policy", "slug": "reassociation-policy", "category": "HR", "department": "Human Resources"},
    {"name": "Relocation Reimbursement Policy", "slug": "relocation-reimbursement", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Rewards and Recognition Policy", "slug": "rewards-recognition", "category": "HR", "department": "Human Resources"},
    {"name": "Separation and Exit Policy", "slug": "separation-exit-policy", "category": "HR", "department": "Human Resources"},
    {"name": "Standard Operating Procedure - Cheques", "slug": "sop-cheques", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "TDS Declaration Process", "slug": "tds-declaration", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Test Paper Accuracy Enhancement Policy", "slug": "test-paper-accuracy", "category": "Quality", "department": "Academic Quality"},
    {"name": "Tools and Vendor Onboarding SOP", "slug": "tools-vendor-onboarding", "category": "Procurement", "department": "Procurement"},
    {"name": "Travel Meal Hotel Reimbursement Policy", "slug": "travel-meal-hotel", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "AI Standard Operating Procedure", "slug": "ai-sop", "category": "IT", "department": "Information Technology"},
    {"name": "Variable Performance Pay and Retention Pay", "slug": "variable-performance-pay", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "VPF Policy", "slug": "vpf-policy", "category": "Finance", "department": "Finance & Accounts"},
    {"name": "Vulnerability Management Policy", "slug": "vulnerability-management", "category": "IT", "department": "Information Technology"},
    {"name": "Wedding Gift Policy", "slug": "wedding-gift-policy", "category": "HR", "department": "Human Resources"},
    {"name": "Whistleblower Policy", "slug": "whistleblower-policy", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Escalate Dont Engage Social Media Policy", "slug": "escalate-social-media", "category": "Compliance", "department": "Legal & Compliance"},
    {"name": "Declaration Form", "slug": "declaration-form", "category": "HR", "department": "Human Resources"},
]


def seed():
    print("\n🌱 PolicyPilot — Database Seeder")
    print("=" * 50)

    with get_db() as db:
        # 1. Create admin user
        admin = db.query(User).filter_by(email=settings.admin_email).first()
        if not admin:
            admin = User(
                name="System Admin",
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
            db.add(admin)
            db.flush()
            print(f"✅ Admin user created: {settings.admin_email}")
        else:
            print(f"ℹ️  Admin user already exists: {settings.admin_email}")

        # 2. Create demo users
        demo_users = [
            {"name": "Priya Sharma", "email": "priya.sharma@pw.live", "role": "employee"},
            {"name": "Rahul Verma", "email": "rahul.verma@pw.live", "role": "manager"},
            {"name": "Meera Nair", "email": "meera.nair@pw.live", "role": "hr"},
        ]
        for u in demo_users:
            if not db.query(User).filter_by(email=u["email"]).first():
                db.add(User(
                    name=u["name"],
                    email=u["email"],
                    password_hash=hash_password("Demo@123!"),
                    role=u["role"],
                ))
                print(f"✅ Demo user: {u['email']} ({u['role']})")

        # 3. Register documents (without ingestion — ingestion is a separate step)
        doc_count = 0
        for doc_data in INITIAL_DOCUMENTS:
            existing = db.query(Document).filter_by(slug=doc_data["slug"]).first()
            if not existing:
                doc = Document(
                    name=doc_data["name"],
                    slug=doc_data["slug"],
                    category=doc_data.get("category"),
                    department=doc_data.get("department"),
                )
                db.add(doc)
                doc_count += 1

        print(f"✅ Registered {doc_count} new documents in database")

    print("\n✅ Seeding complete!")
    print(f"\nAdmin credentials:")
    print(f"  Email:    {settings.admin_email}")
    print(f"  Password: {settings.admin_password}")
    print(f"\nDemo credentials (password: Demo@123!):")
    print(f"  employee: priya.sharma@pw.live")
    print(f"  manager:  rahul.verma@pw.live")
    print(f"  hr:       meera.nair@pw.live")


if __name__ == "__main__":
    seed()
