"""Voice interview API schemas."""
from pydantic import BaseModel, Field, field_validator


class InterviewVoiceOption(BaseModel):
    id: str
    label: str
    provider: str
    tier: str
    language: str | None = None
    gender: str | None = None
    description: str | None = None
    featured: bool = False
    clone_record_id: int | None = None


class InterviewVoiceGroup(BaseModel):
    tier: str
    label: str
    voices: list[InterviewVoiceOption]


class InterviewLanguageOption(BaseModel):
    code: str
    label: str


class InterviewVoicesResponse(BaseModel):
    groups: list[InterviewVoiceGroup]
    languages: list[InterviewLanguageOption]
    default_voice: InterviewVoiceOption
    default_language: str
    # Legacy fields for backward compatibility
    speakers: list[InterviewVoiceOption] = []
    default_speaker: str | None = None


class InterviewVoicePreviewRequest(BaseModel):
    voice_provider: str
    voice_id: str
    text: str = "Hello, I will be your AI interviewer today. Please speak clearly when it is your turn to answer."
    tts_language_code: str = "en-IN"

    @field_validator("voice_provider")
    @classmethod
    def voice_provider_valid(cls, v: str) -> str:
        provider = (v or "").strip().lower()
        if provider not in {"cartesia"}:
            raise ValueError("voice_provider must be cartesia")
        return provider

    @field_validator("voice_id")
    @classmethod
    def voice_id_not_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("voice_id is required")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text is required")
        return v[:500]


class InterviewTtsRequest(BaseModel):
    user_id: int
    interview_id: int
    question_order: int = Field(ge=1)
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text is required")
        return v


class InterviewAnswerCheckpointResponse(BaseModel):
    question_id: int | None = None
    order: int
    question: str
    transcript: str
    answer: str
    audio_key: str | None = None
    audio_url: str | None = None
    audio_presigned_url: str | None = None
    has_audio: bool = False
    duration_ms: int | None = None
    stt_language_code: str | None = None
    saved_at: str | None = None


class InterviewAudioPlaybackResponse(BaseModel):
    order: int
    audio_key: str
    presigned_url: str
    content_type: str = "audio/webm"


class InterviewSessionProgressResponse(BaseModel):
    user_id: int
    interview_id: int
    status: str
    current_question_index: int = 0
    checkpoints: list[InterviewAnswerCheckpointResponse] = []
    answers: list[dict] = []
    voice_provider: str | None = None
    voice_id: str | None = None
    voice_label: str | None = None
    tts_speaker: str | None = None
    tts_language_code: str | None = None
    question_count: int | None = None
    silence_submit_seconds: int = 10
    pause_duration_seconds: int = 10
    max_pauses_per_interview: int = 3
    pauses_used: int = 0
    pauses_remaining: int = 3
    auto_advance_enabled: bool = True


class InterviewVoiceConfigResponse(BaseModel):
    voice_provider: str
    voice_id: str
    voice_label: str
    tts_language_code: str
    stt_language_code: str
    auto_advance_enabled: bool = True
    question_count: int | None = None
    silence_submit_seconds: int = 10
    pause_duration_seconds: int = 10
    max_pauses_per_interview: int = 3
    pauses_used: int = 0
    pauses_remaining: int = 3
    # Legacy
    tts_speaker: str | None = None


class InterviewPauseRequest(BaseModel):
    user_id: int
    interview_id: int


class InterviewPauseResponse(BaseModel):
    user_id: int
    interview_id: int
    pauses_used: int
    pauses_remaining: int
    max_pauses_per_interview: int
    pause_duration_seconds: int


class CustomVoiceCloneResponse(BaseModel):
    id: int
    voice_id: str
    label: str
    provider: str = "cartesia"
    tier: str = "cartesia_custom"
    language: str
    cartesia_language: str
    description: str | None = None
    created_at: str | None = None
