from backend.app.models.job import Job
from backend.app.models.scraper_run import ScraperRun
from backend.app.models.user import User
from backend.app.models.profile import Profile
from backend.app.models.user_resume import UserResume
from backend.app.models.user_job import UserJob
from backend.app.models.career_page_visit import CareerPageVisit
from backend.app.models.form_field_learning import (
    SharedFormStructure,
    SharedSelectorPerformance,
    SharedFieldProfileKey,
    UserFieldAnswer,
    UserSubmissionHistory,
)
from backend.app.models.resume_version import ResumeVersion
from backend.app.models.tailor_context import TailorContext
from backend.app.models.user_resume_preference import UserResumePreference
from backend.app.models.legal_policy import LegalPolicy
from backend.app.models.issue_report import IssueReport
from backend.jobradar.models.application import Application, StatusHistory, SyncStatus
from backend.jobradar.models.nudge import Nudge
from backend.jobradar.models.mock_interview import MockInterviewQuestion, MockInterviewSession, MockInterviewAnswer
from backend.jobradar.models.briefing import CompanyBriefing
