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

_DEFAULT_TERMS_OF_SERVICE = {
    "effective_date": "2026-01-01",
    "company_name": "OpsBrain",
    "contact_email": "legal@opsbrain.com",
    "sections": [
        {
            "id": "acceptance",
            "title": "Acceptance of Terms",
            "content": (
                "Welcome to OpsBrain ('we', 'us', 'our', or the 'Company'). By accessing "
                "or using the OpsBrain platform, website, services, and Chrome extension "
                "(collectively, the 'Service'), you agree to be bound by these Terms of "
                "Service ('Terms'). If you do not agree to these Terms, you may not access "
                "or use the Service.\n\n"
                "These Terms constitute a legally binding agreement between you and OpsBrain. "
                "We reserve the right to modify these Terms at any time. Your continued use "
                "of the Service after changes are posted constitutes acceptance of the "
                "modified Terms."
            ),
        },
        {
            "id": "description",
            "title": "Service Description",
            "content": (
                "OpsBrain is a SaaS platform that provides the following services:\n\n"
                "- **Job Application Tracking:** Track and manage your job applications in one place\n"
                "- **AI-Powered Resume Builder:** Generate, customize, and optimize resumes using AI\n"
                "- **Resume Analysis & ATS Scanning:** Analyze resumes for ATS compatibility and get improvement suggestions\n"
                "- **Interview Preparation:** Practice mock interviews, get AI-powered feedback, and company briefings\n"
                "- **Chrome Extension:** Automated form filling, job tracking, and application management\n"
                "- **Job Recommendations:** AI-powered job matching based on your profile\n"
                "- **Company Research:** Access company insights and career page information\n\n"
                "The Service uses artificial intelligence and third-party APIs to deliver these features. "
                "AI-generated content is provided as suggestions and should be reviewed before use."
            ),
        },
        {
            "id": "eligibility",
            "title": "Eligibility",
            "content": (
                "To use the Service, you must:\n\n"
                "- Be at least 18 years old or the age of majority in your jurisdiction\n"
                "- Have the legal capacity to enter into a binding contract\n"
                "- Not be prohibited from using the Service under applicable law\n"
                "- Provide accurate and complete registration information\n\n"
                "By creating an account, you represent and warrant that you meet these requirements."
            ),
        },
        {
            "id": "account",
            "title": "Account Registration and Security",
            "content": (
                "**Account Creation:**\n"
                "You must create an account to access certain features. You agree to:\n"
                "- Provide accurate, current, and complete information during registration\n"
                "- Maintain and promptly update your account information\n"
                "- Keep your password secure and confidential\n"
                "- Notify us immediately of any unauthorized access to your account\n\n"
                "**Account Responsibility:**\n"
                "You are responsible for all activities that occur under your account. "
                "We are not liable for any loss or damage arising from your failure to "
                "maintain account security. You may not share your account credentials or "
                "allow others to access your account.\n\n"
                "**Account Termination:**\n"
                "We reserve the right to suspend or terminate your account at our discretion, "
                "without notice, for violation of these Terms or for any other reason."
            ),
        },
        {
            "id": "acceptable_use",
            "title": "Acceptable Use Policy",
            "content": (
                "You agree NOT to:\n\n"
                "**Prohibited Activities:**\n"
                "- Use the Service for any unlawful purpose or in violation of these Terms\n"
                "- Impersonate any person or entity or misrepresent your affiliation\n"
                "- Submit false, misleading, or fraudulent information\n"
                "- Interfere with or disrupt the Service or servers/networks connected to the Service\n"
                "- Attempt to gain unauthorized access to any portion of the Service\n"
                "- Use automated systems (bots, scrapers) to access the Service without permission\n"
                "- Reverse engineer, decompile, or disassemble any part of the Service\n"
                "- Remove, obscure, or alter any proprietary notices on the Service\n"
                "- Use the Service to transmit viruses, malware, or harmful code\n"
                "- Violate any applicable laws, regulations, or third-party rights\n\n"
                "**Chrome Extension Usage:**\n"
                "- The extension must only be used for legitimate job search purposes\n"
                "- Do not use the extension to submit false or fraudulent applications\n"
                "- Respect the terms of service of websites where the extension is used\n\n"
                "Violation of this policy may result in immediate account termination."
            ),
        },
        {
            "id": "user_content",
            "title": "User Content and Data",
            "content": (
                "**Content You Provide:**\n"
                "You retain ownership of all content you submit to the Service, including:\n"
                "- Resume data (work history, education, skills, projects)\n"
                "- Job application notes and tracking information\n"
                "- Profile information and preferences\n"
                "- Uploaded files (resumes, cover letters)\n\n"
                "**License to OpsBrain:**\n"
                "By submitting content, you grant OpsBrain a worldwide, non-exclusive, "
                "royalty-free license to use, store, process, and display your content solely "
                "for the purpose of providing and improving the Service. This includes:\n"
                "- Processing your data through AI models to generate resumes and recommendations\n"
                "- Storing your content on our servers and third-party infrastructure (AWS S3)\n"
                "- Analyzing aggregated, anonymized data to improve our algorithms\n\n"
                "**Content Standards:**\n"
                "You represent that your content:\n"
                "- Is accurate and truthful to the best of your knowledge\n"
                "- Does not infringe on any third-party intellectual property rights\n"
                "- Does not contain confidential information belonging to others\n"
                "- Complies with all applicable laws and regulations\n\n"
                "We reserve the right to remove any content that violates these Terms."
            ),
        },
        {
            "id": "payment",
            "title": "Payment and Subscriptions",
            "content": (
                "**Pricing:**\n"
                "OpsBrain offers both free and paid subscription plans. Pricing is displayed "
                "on our website and is subject to change with 30 days' notice to existing subscribers.\n\n"
                "**Payment Processing:**\n"
                "Payments are processed through Razorpay, a third-party payment processor. "
                "By providing payment information, you authorize us to charge the applicable fees. "
                "All payment information is handled directly by Razorpay under their terms and privacy policy.\n\n"
                "**Subscription Terms:**\n"
                "- Subscriptions automatically renew unless cancelled before the renewal date\n"
                "- You can cancel your subscription at any time from your account settings\n"
                "- Cancellations take effect at the end of the current billing period\n"
                "- No refunds are provided for partial subscription periods\n\n"
                "**Refund Policy:**\n"
                "All sales are final. We do not offer refunds except as required by law or "
                "at our sole discretion. If you believe you are entitled to a refund, contact "
                "us at legal@opsbrain.com with your account details and reason.\n\n"
                "**Failed Payments:**\n"
                "If a payment fails, we may suspend or downgrade your account until payment is received."
            ),
        },
        {
            "id": "intellectual_property",
            "title": "Intellectual Property Rights",
            "content": (
                "**OpsBrain Ownership:**\n"
                "The Service, including all software, designs, text, graphics, logos, icons, "
                "images, audio clips, data compilations, and other materials, is owned by "
                "OpsBrain or its licensors and is protected by copyright, trademark, and other "
                "intellectual property laws.\n\n"
                "**Limited License:**\n"
                "Subject to these Terms, we grant you a limited, non-exclusive, non-transferable, "
                "revocable license to access and use the Service for your personal, non-commercial "
                "job search purposes.\n\n"
                "**Trademarks:**\n"
                "OpsBrain and associated logos are trademarks of OpsBrain. You may "
                "not use these trademarks without our prior written consent.\n\n"
                "**AI-Generated Content:**\n"
                "Content generated by our AI features (resumes, cover letters, recommendations) "
                "is provided to you for your use. However, you acknowledge that similar content "
                "may be generated for other users based on similar inputs."
            ),
        },
        {
            "id": "third_party",
            "title": "Third-Party Services and Links",
            "content": (
                "The Service integrates with and links to third-party services:\n\n"
                "**Third-Party APIs:**\n"
                "- **OpenAI:** Powers AI resume generation and analysis\n"
                "- **AWS (Amazon Web Services):** Cloud hosting and file storage\n"
                "- **Razorpay:** Payment processing\n"
                "- **Google OAuth:** Optional login and Gmail integration\n\n"
                "**External Links:**\n"
                "The Service may contain links to third-party websites and job boards. "
                "We are not responsible for the content, privacy practices, or terms of "
                "service of external sites. Your use of third-party services is governed "
                "by their respective terms.\n\n"
                "**No Endorsement:**\n"
                "Inclusion of third-party content or links does not imply endorsement or "
                "recommendation by OpsBrain."
            ),
        },
        {
            "id": "disclaimers",
            "title": "Disclaimers and Limitations",
            "content": (
                "**No Employment Guarantee:**\n"
                "OpsBrain is a tool to assist with job searching. We do NOT guarantee job "
                "offers, interviews, or employment outcomes. Success depends on many factors "
                "outside our control.\n\n"
                "**AI Limitations:**\n"
                "AI-generated content (resumes, recommendations, interview answers) is provided "
                "as suggestions only. You are responsible for reviewing, verifying, and editing "
                "all AI-generated content before use. We do not guarantee accuracy, completeness, "
                "or suitability of AI outputs.\n\n"
                "**Service Availability:**\n"
                "The Service is provided on an 'AS IS' and 'AS AVAILABLE' basis. We do not "
                "warrant that the Service will be uninterrupted, error-free, secure, or free "
                "of viruses or other harmful components.\n\n"
                "**No Professional Advice:**\n"
                "The Service does not constitute professional career counseling, legal advice, "
                "or financial advice. Consult qualified professionals for specialized guidance.\n\n"
                "**Data Accuracy:**\n"
                "While we strive for accuracy, we do not warrant the accuracy, completeness, "
                "or reliability of company data, job listings, or salary information displayed "
                "in the Service."
            ),
        },
        {
            "id": "limitation_liability",
            "title": "Limitation of Liability",
            "content": (
                "TO THE MAXIMUM EXTENT PERMITTED BY LAW:\n\n"
                "**No Consequential Damages:**\n"
                "OpsBrain, its officers, directors, employees, and agents shall NOT be liable "
                "for any indirect, incidental, special, consequential, or punitive damages, "
                "including but not limited to:\n"
                "- Loss of employment opportunities or job offers\n"
                "- Loss of profits, revenue, or business opportunities\n"
                "- Loss of data or content\n"
                "- Cost of procurement of substitute services\n"
                "- Damage to reputation or professional standing\n\n"
                "**Aggregate Liability Cap:**\n"
                "Our total aggregate liability arising out of or relating to these Terms or "
                "the Service shall not exceed the greater of (a) $100 USD or (b) the amount "
                "you paid to OpsBrain in the 12 months preceding the claim.\n\n"
                "**Basis of Bargain:**\n"
                "These limitations reflect the allocation of risk between you and OpsBrain. "
                "The limitations apply even if any remedy fails its essential purpose."
            ),
        },
        {
            "id": "indemnification",
            "title": "Indemnification",
            "content": (
                "You agree to indemnify, defend, and hold harmless OpsBrain, its affiliates, "
                "officers, directors, employees, agents, and licensors from and against any "
                "and all claims, liabilities, damages, losses, costs, expenses, or fees "
                "(including reasonable attorneys' fees) arising from:\n\n"
                "- Your use or misuse of the Service\n"
                "- Your violation of these Terms\n"
                "- Your violation of any third-party rights, including intellectual property rights\n"
                "- Your content or data submitted to the Service\n"
                "- Any fraudulent, misleading, or false information you provide\n\n"
                "We reserve the right to assume the exclusive defense and control of any matter "
                "subject to indemnification by you, at your expense."
            ),
        },
        {
            "id": "termination",
            "title": "Termination",
            "content": (
                "**By You:**\n"
                "You may terminate your account at any time by deleting it from your account "
                "settings or by contacting us at legal@opsbrain.com. Termination does not "
                "relieve you of obligations incurred prior to termination.\n\n"
                "**By OpsBrain:**\n"
                "We may suspend or terminate your access to the Service at any time, with or "
                "without cause, with or without notice, at our sole discretion. Grounds for "
                "termination include, but are not limited to:\n"
                "- Violation of these Terms or Acceptable Use Policy\n"
                "- Fraudulent or illegal activity\n"
                "- Failure to pay applicable fees\n"
                "- Extended period of inactivity\n"
                "- Upon your request\n\n"
                "**Effect of Termination:**\n"
                "Upon termination:\n"
                "- Your right to access and use the Service immediately ceases\n"
                "- Your data will be deleted according to our data retention policy (within 30 days)\n"
                "- You remain liable for all charges incurred prior to termination\n"
                "- Sections of these Terms that by their nature should survive termination shall survive"
            ),
        },
        {
            "id": "privacy",
            "title": "Privacy and Data Protection",
            "content": (
                "Your use of the Service is also governed by our Privacy Policy, which is "
                "incorporated into these Terms by reference. By using the Service, you consent "
                "to our collection, use, and disclosure of your information as described in "
                "the Privacy Policy.\n\n"
                "**Key Points:**\n"
                "- We collect personal information you provide and usage data\n"
                "- Your resume and profile data is processed through AI models (OpenAI)\n"
                "- Data is stored on secure servers (AWS S3) with encryption\n"
                "- We do not sell your personal data to third parties\n"
                "- You have rights to access, correct, and delete your data\n\n"
                "For complete details, please review our Privacy Policy at /privacy-policy."
            ),
        },
        {
            "id": "governing_law",
            "title": "Governing Law and Dispute Resolution",
            "content": (
                "**Governing Law:**\n"
                "These Terms shall be governed by and construed in accordance with the laws "
                "of [Your Jurisdiction], without regard to its conflict of law provisions.\n\n"
                "**Dispute Resolution:**\n"
                "In the event of any dispute, claim, or controversy arising out of or relating "
                "to these Terms or the Service, you agree to first attempt to resolve the "
                "dispute informally by contacting us at legal@hiremate.com.\n\n"
                "**Arbitration:**\n"
                "If informal resolution is unsuccessful within 60 days, disputes shall be "
                "resolved by binding arbitration in accordance with the rules of [Arbitration Body]. "
                "The arbitration shall be conducted in English. Each party shall bear its own costs.\n\n"
                "**Class Action Waiver:**\n"
                "You agree to bring claims only in your individual capacity and not as a "
                "plaintiff or class member in any purported class, consolidated, or representative proceeding.\n\n"
                "**Exceptions:**\n"
                "Either party may seek injunctive relief in court for intellectual property "
                "infringement or unauthorized access to the Service."
            ),
        },
        {
            "id": "miscellaneous",
            "title": "Miscellaneous",
            "content": (
                "**Entire Agreement:**\n"
                "These Terms, together with the Privacy Policy, constitute the entire agreement "
                "between you and OpsBrain regarding the Service and supersede all prior agreements.\n\n"
                "**Modifications:**\n"
                "We reserve the right to modify these Terms at any time. Changes will be posted "
                "on this page with an updated 'Last Updated' date. Material changes will be "
                "communicated via email or prominent notice in the Service.\n\n"
                "**Severability:**\n"
                "If any provision of these Terms is found to be invalid or unenforceable, the "
                "remaining provisions shall remain in full force and effect.\n\n"
                "**Waiver:**\n"
                "No waiver of any term shall be deemed a further or continuing waiver of such "
                "term or any other term. Our failure to enforce any right or provision shall "
                "not constitute a waiver of such right or provision.\n\n"
                "**Assignment:**\n"
                "You may not assign or transfer these Terms or your account without our prior "
                "written consent. We may assign these Terms without restriction.\n\n"
                "**Force Majeure:**\n"
                "We shall not be liable for any failure to perform due to circumstances beyond "
                "our reasonable control, including acts of God, natural disasters, war, terrorism, "
                "strikes, or internet outages."
            ),
        },
        {
            "id": "contact",
            "title": "Contact Information",
            "content": (
                "If you have questions, concerns, or requests regarding these Terms of Service, "
                "please contact us:\n\n"
                "**Email:** legal@opsbrain.com\n"
                "**Subject line:** Terms of Service Inquiry\n\n"
                "For technical support: support@opsbrain.com\n"
                "For privacy matters: privacy@opsbrain.com\n\n"
                "We aim to respond to all inquiries within 5 business days."
            ),
        },
    ],
}

_DEFAULT_PRIVACY_POLICY = {
    "effective_date": "2026-01-01",
    "company_name": "OpsBrain",
    "contact_email": "privacy@opsbrain.com",
    "sections": [
        {
            "id": "introduction",
            "title": "Introduction",
            "content": (
                "Welcome to OpsBrain ('we', 'us', or 'our'). OpsBrain is a SaaS platform "
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
                "**Chrome Extension:**\n"
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
                "- Provide, operate, and maintain the OpsBrain platform\n"
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
                "To exercise any of these rights, contact us at privacy@opsbrain.com. "
                "We will respond within 30 days."
            ),
        },
        {
            "id": "contact",
            "title": "Contact Information",
            "content": (
                "If you have questions, concerns, or requests related to this Privacy "
                "Policy, please contact us:\n\n"
                "**Email:** privacy@opsbrain.com\n"
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

    @staticmethod
    def seed_default_terms_of_service(db: Session) -> None:
        """Called on startup — inserts default TOS only if none exists."""
        existing = (
            db.query(LegalPolicy)
            .filter(LegalPolicy.type == "terms_of_service")
            .first()
        )
        if existing:
            return
        LegalService.upsert_policy(
            db,
            policy_type="terms_of_service",
            version="1.0",
            title="Terms of Service",
            content=_DEFAULT_TERMS_OF_SERVICE,
        )
