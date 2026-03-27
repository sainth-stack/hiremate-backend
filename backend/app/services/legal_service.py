"""
LegalService — CRUD for versioned legal policies (privacy policy, terms of service).
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.models.legal_policy import LegalPolicy

# ---------------------------------------------------------------------------
# Default content seeded on first startup
# ---------------------------------------------------------------------------

_DEFAULT_PRIVACY_POLICY = {
    "effective_date": "2026-01-01",
    "company_name": "HireMate",
    "contact_email": "privacy@hiremate.com",
    "sections": [
        {
            "id": "introduction",
            "title": "Introduction",
            "content": (
                "Welcome to HireMate ('we', 'us', or 'our'). HireMate is a SaaS platform "
                "that helps job seekers manage their job search, build AI-powered resumes, "
                "and automate form filling via our Chrome extension. This Privacy Policy "
                "explains how we collect, use, disclose, and safeguard your information "
                "when you use our services. Please read this policy carefully. If you "
                "disagree with its terms, please discontinue use of our platform."
            ),
        },
        {
            "id": "data_collection",
            "title": "Data We Collect",
            "content": (
                "We collect several categories of information:\n\n"
                "**Information you provide directly:**\n"
                "- Account registration data (name, email, password)\n"
                "- Resume and profile data (work history, education, skills, projects)\n"
                "- Job application data and notes you enter\n"
                "- Support or feedback submissions\n\n"
                "**Information collected automatically:**\n"
                "- Usage logs: pages visited, features used, timestamps\n"
                "- Device and browser metadata (browser type, OS, screen resolution)\n"
                "- IP address and approximate geographic location\n\n"
                "**Chrome Extension (OpsBrain):**\n"
                "- URLs of career/job pages you visit (to track applications)\n"
                "- Form field structures and your answers (stored to enable autofill)\n"
                "- Screenshots you explicitly capture for issue reporting"
            ),
        },
        {
            "id": "use_of_data",
            "title": "How We Use Your Data",
            "content": (
                "We use the information we collect to:\n\n"
                "- Provide, operate, and maintain the HireMate platform\n"
                "- Personalize your resume and job-search experience using AI\n"
                "- Power autofill functionality in the Chrome extension\n"
                "- Track and display your job application pipeline\n"
                "- Analyze usage patterns to improve features and fix bugs\n"
                "- Send transactional emails (account confirmations, password resets)\n"
                "- Respond to support requests and issue reports\n"
                "- Detect, prevent, and address fraud or security incidents\n\n"
                "We do **not** sell your personal data to third parties."
            ),
        },
        {
            "id": "cookies",
            "title": "Cookies & Tracking",
            "content": (
                "We use cookies and similar tracking technologies to enhance your "
                "experience:\n\n"
                "- **Essential cookies:** Required for authentication and session management\n"
                "- **Analytics cookies:** Help us understand how users interact with our "
                "platform (e.g., page views, feature usage)\n"
                "- **Preference cookies:** Store your UI preferences (theme, layout)\n\n"
                "The Chrome extension uses `chrome.storage.local` for token and preference "
                "storage — this is scoped to the extension and not shared with websites.\n\n"
                "You can control cookie behaviour through your browser settings. Disabling "
                "essential cookies may impair login functionality."
            ),
        },
        {
            "id": "third_party",
            "title": "Third-Party Services",
            "content": (
                "We integrate with the following third-party services, each governed by "
                "their own privacy policies:\n\n"
                "- **OpenAI:** Powers AI resume generation and analysis. Resume content "
                "may be sent to OpenAI's API for processing.\n"
                "- **Amazon Web Services (S3):** Stores uploaded resumes and screenshots\n"
                "- **Razorpay:** Processes payments. Payment data is handled directly by "
                "Razorpay and not stored on our servers.\n"
                "- **Redis:** Used as a cache layer for performance; does not store "
                "persistent personal data.\n\n"
                "We encourage you to review each provider's privacy policy."
            ),
        },
        {
            "id": "retention",
            "title": "Data Retention",
            "content": (
                "We retain your personal data for as long as your account is active or "
                "as needed to provide services. Specifically:\n\n"
                "- **Account data:** Retained until you delete your account\n"
                "- **Resume files:** Retained until you delete them or your account\n"
                "- **Usage logs:** Retained for up to 12 months for analytics\n"
                "- **Extension form-learning data:** Retained until you clear it from "
                "settings or delete your account\n"
                "- **Issue reports:** Retained indefinitely for support and quality purposes\n\n"
                "On account deletion, personal identifiers are removed within 30 days, "
                "subject to legal retention requirements."
            ),
        },
        {
            "id": "security",
            "title": "Security",
            "content": (
                "We implement industry-standard security measures to protect your data:\n\n"
                "- Passwords are hashed using Argon2 (never stored in plaintext)\n"
                "- API access requires signed JWT tokens with short expiry windows\n"
                "- Data in transit is encrypted via TLS/HTTPS\n"
                "- S3 files are stored with server-side encryption\n"
                "- Access to production systems is restricted by role\n\n"
                "Despite these measures, no method of transmission over the internet is "
                "100% secure. We cannot guarantee absolute security, and you use the "
                "service at your own risk."
            ),
        },
        {
            "id": "user_rights",
            "title": "Your Rights",
            "content": (
                "Depending on your jurisdiction, you may have the following rights:\n\n"
                "- **Access:** Request a copy of the personal data we hold about you\n"
                "- **Correction:** Request correction of inaccurate data\n"
                "- **Deletion:** Request deletion of your account and associated data\n"
                "- **Portability:** Receive your data in a structured, machine-readable format\n"
                "- **Objection:** Object to certain processing activities\n"
                "- **Withdraw consent:** Where processing is based on consent, withdraw it "
                "at any time\n\n"
                "To exercise any of these rights, contact us at privacy@hiremate.com. "
                "We will respond within 30 days."
            ),
        },
        {
            "id": "contact",
            "title": "Contact Information",
            "content": (
                "If you have questions, concerns, or requests related to this Privacy "
                "Policy, please contact us:\n\n"
                "**Email:** privacy@hiremate.com\n"
                "**Subject line:** Privacy Policy Request\n\n"
                "We are committed to resolving privacy concerns promptly and transparently."
            ),
        },
    ],
}


class LegalService:
    @staticmethod
    def get_current_policy(db: Session, policy_type: str = "privacy_policy") -> Optional[LegalPolicy]:
        return (
            db.query(LegalPolicy)
            .filter(LegalPolicy.type == policy_type, LegalPolicy.is_current.is_(True))
            .first()
        )

    @staticmethod
    def get_policy_history(db: Session, policy_type: str = "privacy_policy") -> List[LegalPolicy]:
        return (
            db.query(LegalPolicy)
            .filter(LegalPolicy.type == policy_type)
            .order_by(LegalPolicy.created_at.desc())
            .all()
        )

    @staticmethod
    def upsert_policy(
        db: Session,
        policy_type: str,
        version: str,
        title: str,
        content: dict,
    ) -> LegalPolicy:
        # Mark all existing as not current
        db.query(LegalPolicy).filter(LegalPolicy.type == policy_type).update(
            {"is_current": False}
        )
        policy = LegalPolicy(
            type=policy_type,
            version=version,
            title=title,
            content=content,
            is_current=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        return policy

    @staticmethod
    def seed_default_privacy_policy(db: Session) -> None:
        """Called on startup — inserts default policy only if none exists."""
        existing = (
            db.query(LegalPolicy)
            .filter(LegalPolicy.type == "privacy_policy")
            .first()
        )
        if existing:
            return
        LegalService.upsert_policy(
            db,
            policy_type="privacy_policy",
            version="1.0",
            title="Privacy Policy",
            content=_DEFAULT_PRIVACY_POLICY,
        )
