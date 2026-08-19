"""Interview voice endpoints — Sarvam STT, Cartesia Premium TTS, session checkpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user, get_db
from backend.app.core.logging_config import get_logger
from backend.app.models.interview import Interview
from backend.app.models.user import User
from backend.app.schemas.voice import (
    CustomVoiceCloneResponse,
    InterviewAnswerCheckpointResponse,
    InterviewAudioPlaybackResponse,
    InterviewMediaPlaybackResponse,
    InterviewPauseRequest,
    InterviewPauseResponse,
    InterviewSessionProgressResponse,
    InterviewTtsRequest,
    InterviewVoiceConfigResponse,
    InterviewVoiceGroup,
    InterviewVoiceOption,
    InterviewVoicePreviewRequest,
    InterviewVoicesResponse,
)
from backend.app.services.interview_assignment import (
    get_user_assignment,
    normalize_assignment_status,
    resolve_interview_subject_user,
)
from backend.app.services.interview_request_service import mark_request_in_progress
from backend.app.services.voice.audio_lookup import (
    find_answer_media,
    media_filename,
    resolve_stream_key,
)
from backend.app.services.voice.media_storage import (
    UnplayableMediaError,
    cache_playback_mp3,
    get_presigned_media_url,
    guess_audio_content_type,
    is_playable_media,
    load_stream_bytes,
    upload_interview_answer_audio,
    upload_interview_answer_video,
)
from backend.app.services.voice.cartesia_service import (
    CLONE_ALLOWED_EXTENSIONS,
    cartesia_language_for_voice,
    get_grouped_interview_voices,
    normalize_cartesia_voice_id,
)
from backend.app.services.voice.custom_voice_service import (
    allowed_custom_voice_ids,
    create_custom_voice_clone,
    custom_voice_to_option,
    list_active_custom_voices,
    soft_delete_custom_voice_clone,
)
from backend.app.services.voice.sarvam_service import transcribe_audio
from backend.app.services.voice.session_config import resolve_session_config
from backend.app.services.voice.session_store import (
    get_pause_state,
    get_session_progress,
    record_interview_pause,
    save_answer_checkpoint,
    update_answer_playback_cache,
)
from backend.app.services.voice.voice_config import (
    LaunchVoiceConfig,
    resolve_assignment_voice_config,
    resolve_question_count,
    synthesize_launch_speech,
)

router = APIRouter()
logger = get_logger("api.interview.voice")

MAX_CLONE_CLIP_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 150 * 1024 * 1024


def _media_urls(request: Request, *, user_id: int, interview_id: int, order: int, kind: str) -> dict[str, str]:
    base = str(request.base_url).rstrip("/")
    api_base = f"{base}/api/interview/voice/media/stream"
    common = f"user_id={user_id}&interview_id={interview_id}&order={order}&kind={kind}"
    return {
        "stream_url": f"{api_base}?{common}",
        "download_url": f"{api_base}?{common}&download=true",
    }


def _enrich_checkpoint_media(entry: dict, request: Request | None, user_id: int, interview_id: int) -> dict:
    data = dict(entry)
    order = int(data.get("order") or 0)
    data["has_audio"] = bool(data.get("audio_key"))
    data["has_video"] = bool(data.get("video_key"))
    playback_key = data.get("audio_playback_key") or data.get("audio_key")
    if playback_key:
        try:
            content_type = "audio/mpeg" if data.get("audio_playback_key") else guess_audio_content_type(data.get("audio_key"))
            data["audio_presigned_url"] = get_presigned_media_url(playback_key, content_type=content_type)
        except Exception:
            data["audio_presigned_url"] = None
    if request and order:
        if data.get("has_audio"):
            data.update(_media_urls(request, user_id=user_id, interview_id=interview_id, order=order, kind="audio"))
        if data.get("has_video"):
            video_urls = _media_urls(request, user_id=user_id, interview_id=interview_id, order=order, kind="video")
            data["video_stream_url"] = video_urls["stream_url"]
            data["video_download_url"] = video_urls["download_url"]
    return data


def _checkpoint_response(
    entry: dict,
    request: Request,
    user_id: int,
    interview_id: int,
    *,
    presigned_url: str | None = None,
) -> InterviewAnswerCheckpointResponse:
    data = _enrich_checkpoint_media(entry, request, user_id, interview_id)
    if presigned_url and not data.get("audio_presigned_url"):
        data["audio_presigned_url"] = presigned_url
    allowed = set(InterviewAnswerCheckpointResponse.model_fields.keys())
    return InterviewAnswerCheckpointResponse(**{key: data[key] for key in allowed if key in data})


def _require_admin(current_user: User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def _clone_response(record) -> CustomVoiceCloneResponse:
    option = custom_voice_to_option(record)
    return CustomVoiceCloneResponse(
        id=record.id,
        voice_id=option["id"],
        label=option["label"],
        provider=option["provider"],
        tier=option["tier"],
        language=option["language"],
        cartesia_language=option["cartesia_language"],
        description=option.get("description"),
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


def _voice_config_response(db: Session, user_id: int, interview_id: int) -> tuple:
    assignment, launch = get_user_assignment(db, user_id, interview_id)
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    voice = resolve_assignment_voice_config(db, user_id, interview_id)
    question_count = resolve_question_count(interview, launch)
    session_config = resolve_session_config(launch)
    pause_state = get_pause_state(assignment, session_config)
    return assignment, launch, interview, voice, question_count, session_config, pause_state


def _session_fields(session_config, pause_state) -> dict:
    return {
        "silence_submit_seconds": session_config.silence_submit_seconds,
        "pause_duration_seconds": session_config.pause_duration_seconds,
        "max_pauses_per_interview": session_config.max_pauses_per_interview,
        "auto_advance_enabled": session_config.auto_advance_enabled,
        "pauses_used": pause_state["pauses_used"],
        "pauses_remaining": pause_state["pauses_remaining"],
    }


@router.get("/voices", response_model=InterviewVoicesResponse)
def list_interview_voices(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """List grouped Cartesia premium and custom cloned voices for launch configuration."""
    custom_options = [custom_voice_to_option(voice) for voice in list_active_custom_voices(db)]
    catalog = get_grouped_interview_voices(custom_options)
    groups = [InterviewVoiceGroup(**group) for group in catalog["groups"]]
    default_voice = InterviewVoiceOption(**catalog["default_voice"])
    return InterviewVoicesResponse(
        groups=groups,
        languages=catalog["languages"],
        default_voice=default_voice,
        default_language=catalog["default_language"],
        speakers=[],
        default_speaker=None,
    )


@router.post("/voices/clone", response_model=CustomVoiceCloneResponse)
async def clone_interview_voice(
    clip: UploadFile = File(...),
    name: str = Form(...),
    cartesia_language: str = Form("en"),
    tts_language_code: str = Form("en-IN"),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone a new interviewer voice from a short audio sample (admin only)."""
    _require_admin(current_user)

    filename = (clip.filename or "clip.wav").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{extension}" not in CLONE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format. Use one of: {', '.join(sorted(CLONE_ALLOWED_EXTENSIONS))}",
        )

    clip_bytes = await clip.read()
    if not clip_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio clip is empty")
    if len(clip_bytes) > MAX_CLONE_CLIP_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio clip must be 10 MB or smaller")

    language = cartesia_language.strip().lower()
    if language not in {"en", "hi"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cartesia_language must be en or hi")

    try:
        record = create_custom_voice_clone(
            db,
            clip_bytes=clip_bytes,
            filename=filename,
            name=name,
            cartesia_language=language,
            tts_language_code=tts_language_code.strip() or "en-IN",
            description=description,
            created_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice clone failed: {exc}",
        ) from exc

    return _clone_response(record)


@router.delete("/voices/clone/{clone_id}", response_model=CustomVoiceCloneResponse)
def delete_interview_voice_clone(
    clone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a custom cloned voice (admin only)."""
    _require_admin(current_user)
    record = soft_delete_custom_voice_clone(db, clone_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom voice not found")
    return _clone_response(record)


@router.get("/voice-config", response_model=InterviewVoiceConfigResponse)
def get_interview_voice_config(
    user_id: int = Query(...),
    interview_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    _assignment, _launch, _interview, voice, question_count, session_config, pause_state = _voice_config_response(
        db, subject_user_id, interview_id,
    )
    return InterviewVoiceConfigResponse(
        voice_provider=voice.provider,
        voice_id=voice.voice_id,
        voice_label=voice.display_name,
        tts_language_code=voice.language_code,
        stt_language_code=voice.language_code,
        question_count=question_count,
        tts_speaker=voice.voice_id if voice.provider == "sarvam" else None,
        **_session_fields(session_config, pause_state),
    )


@router.get("/session/progress", response_model=InterviewSessionProgressResponse)
def get_interview_session_progress(
    request: Request,
    user_id: int = Query(...),
    interview_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch, _interview, voice, question_count, session_config, pause_state = _voice_config_response(
        db, subject_user_id, interview_id,
    )
    progress = get_session_progress(assignment)
    checkpoints = []
    for item in progress.get("checkpoints") or []:
        checkpoints.append(_checkpoint_response(dict(item), request, subject_user_id, interview_id))
    return InterviewSessionProgressResponse(
        user_id=subject_user_id,
        interview_id=interview_id,
        status=normalize_assignment_status(assignment.status),
        current_question_index=progress.get("current_question_index") or 0,
        checkpoints=checkpoints,
        answers=progress.get("answers") or [],
        voice_provider=voice.provider,
        voice_id=voice.voice_id,
        voice_label=voice.display_name,
        tts_speaker=voice.voice_id if voice.provider == "sarvam" else None,
        tts_language_code=voice.language_code,
        question_count=question_count,
        **_session_fields(session_config, pause_state),
    )


@router.post("/voice/pause", response_model=InterviewPauseResponse)
def consume_interview_pause(
    body: InterviewPauseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record one thinking pause for the interview session (whole-interview limit)."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, body.user_id, body.interview_id, read_only=False,
    )
    assignment, launch = get_user_assignment(db, subject_user_id, body.interview_id)

    if normalize_assignment_status(assignment.status) == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")

    session_config = resolve_session_config(launch)
    try:
        pause_state = record_interview_pause(db, assignment, session_config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return InterviewPauseResponse(
        user_id=subject_user_id,
        interview_id=body.interview_id,
        **pause_state,
    )


@router.post("/voice/preview")
def preview_interview_voice(
    body: InterviewVoicePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview a launch voice before assigning candidates (admin only)."""
    _require_admin(current_user)

    allowed_custom = allowed_custom_voice_ids(db)
    custom_languages = {
        voice.cartesia_voice_id: voice.cartesia_language for voice in list_active_custom_voices(db)
    }
    voice_id = body.voice_id.strip()
    cartesia_uuid = normalize_cartesia_voice_id(voice_id, allowed_custom_ids=allowed_custom)
    voice = LaunchVoiceConfig(
        provider="cartesia",
        voice_id=voice_id if voice_id.startswith("custom:") else cartesia_uuid,
        voice_label=voice_id,
        language_code=body.tts_language_code or settings.sarvam_default_language,
        cartesia_language=cartesia_language_for_voice(
            voice_id,
            custom_languages=custom_languages,
        ),
    )
    try:
        audio_bytes = synthesize_launch_speech(text=body.text, voice=voice, db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice preview failed: {exc}",
        ) from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/voice/tts")
def synthesize_interview_question(
    body: InterviewTtsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate TTS audio using the launch campaign's selected voice."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, body.user_id, body.interview_id, read_only=False,
    )
    voice = resolve_assignment_voice_config(db, subject_user_id, body.interview_id)
    try:
        audio_bytes = synthesize_launch_speech(text=body.text, voice=voice, db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS generation failed: {exc}",
        ) from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/voice/answer", response_model=InterviewAnswerCheckpointResponse)
async def submit_interview_voice_answer(
    request: Request,
    user_id: int = Form(...),
    interview_id: int = Form(...),
    question_id: int | None = Form(None),
    question_order: int = Form(...),
    question_text: str = Form(...),
    duration_ms: int | None = Form(None),
    video_duration_ms: int | None = Form(None),
    current_question_index: int | None = Form(None),
    client_transcript: str | None = Form(None),
    audio: UploadFile = File(...),
    video: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload answer audio, transcribe via Sarvam STT, store in S3, and save checkpoint."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=False,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)

    if normalize_assignment_status(assignment.status) == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")

    mark_request_in_progress(db, subject_user_id, interview_id)
    voice = resolve_assignment_voice_config(db, subject_user_id, interview_id)

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    content_type = audio.content_type or "audio/webm"
    filename = audio.filename or f"answer_q{question_order}.webm"
    fallback_transcript = (client_transcript or "").strip()
    min_client_transcript_chars = 3
    audio_valid = is_playable_media(audio_bytes, kind="audio")

    if not audio_valid and len(fallback_transcript) < min_client_transcript_chars:
        raise HTTPException(
            status_code=400,
            detail="Invalid audio recording — please record again and submit.",
        )

    stt_result: dict
    if not audio_valid:
        stt_result = {
            "transcript": fallback_transcript,
            "language_code": voice.language_code,
        }
    elif len(fallback_transcript) >= min_client_transcript_chars:
        stt_result = {
            "transcript": fallback_transcript,
            "language_code": voice.language_code,
        }
    else:
        try:
            stt_result = transcribe_audio(
                audio_bytes=audio_bytes,
                filename=filename,
                content_type=content_type,
                language_code=voice.language_code,
                client_transcript=client_transcript,
            )
        except Exception as exc:
            if fallback_transcript:
                stt_result = {
                    "transcript": fallback_transcript,
                    "language_code": voice.language_code,
                }
            else:
                logger.warning("STT failed with no client transcript: %s", exc)
                stt_result = {
                    "transcript": "",
                    "language_code": voice.language_code,
                }

    transcript = (stt_result.get("transcript") or "").strip()
    stt_result["transcript"] = transcript
    stt_result["answer"] = transcript

    audio_key = None
    audio_url = None
    audio_playback_key = None
    audio_playback_url = None
    presigned_url = None
    if audio_valid:
        try:
            storage = upload_interview_answer_audio(
                audio_bytes=audio_bytes,
                user_id=subject_user_id,
                interview_id=interview_id,
                assignment_id=assignment.id,
                question_order=question_order,
                mime_type=content_type,
            )
            audio_key = storage["key"]
            audio_url = storage["url"]
            audio_playback_key = storage.get("playback_key")
            audio_playback_url = storage.get("playback_url")
            presigned_url = storage.get("presigned_url")
        except Exception as exc:
            if not fallback_transcript and not transcript:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Audio storage failed: {exc}",
                ) from exc
            logger.warning("Audio storage failed, saving transcript-only checkpoint: %s", exc)

    video_key = None
    video_url = None
    video_playback_key = None
    video_playback_url = None
    if video is not None:
        video_bytes = await video.read()
        if video_bytes:
            if len(video_bytes) > MAX_VIDEO_BYTES:
                raise HTTPException(status_code=400, detail="Video file too large (max 150MB)")
            video_type = video.content_type or "video/webm"
            try:
                video_storage = upload_interview_answer_video(
                    video_bytes=video_bytes,
                    user_id=subject_user_id,
                    interview_id=interview_id,
                    assignment_id=assignment.id,
                    question_order=question_order,
                    mime_type=video_type,
                )
                video_key = video_storage["key"]
                video_url = video_storage["url"]
                video_playback_key = video_storage.get("playback_key")
                video_playback_url = video_storage.get("playback_url")
            except Exception as exc:
                if not fallback_transcript and not audio_key:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Video storage failed: {exc}",
                    ) from exc

    checkpoint = save_answer_checkpoint(
        db,
        assignment,
        question_id=question_id,
        question_order=question_order,
        question_text=question_text.strip(),
        transcript=transcript,
        audio_key=audio_key,
        audio_url=audio_url,
        audio_playback_key=audio_playback_key,
        audio_playback_url=audio_playback_url,
        video_key=video_key,
        video_url=video_url,
        video_playback_key=video_playback_key,
        video_playback_url=video_playback_url,
        duration_ms=duration_ms,
        video_duration_ms=video_duration_ms,
        stt_language_code=stt_result.get("language_code") or voice.language_code,
        current_question_index=current_question_index,
    )

    return _checkpoint_response(
        checkpoint,
        request,
        subject_user_id,
        interview_id,
        presigned_url=presigned_url,
    )


@router.get("/voice/audio", response_model=InterviewAudioPlaybackResponse)
def get_interview_answer_audio(
    request: Request,
    user_id: int = Query(...),
    interview_id: int = Query(...),
    order: int = Query(..., ge=1),
    download: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return playback/download URLs for a stored answer recording."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)
    submission = assignment.submission_data if isinstance(assignment.submission_data, dict) else {}
    media_item = find_answer_media(submission, order=order)
    if not media_item or not media_item.get("audio_key"):
        raise HTTPException(status_code=404, detail="Answer recording not found")

    stream_key, content_type = resolve_stream_key(media_item, kind="audio")
    if not stream_key:
        raise HTTPException(status_code=404, detail="Answer recording not found")

    filename = media_filename(order, "audio", content_type)
    urls = _media_urls(request, user_id=subject_user_id, interview_id=interview_id, order=order, kind="audio")
    return InterviewAudioPlaybackResponse(
        order=order,
        audio_key=str(media_item["audio_key"]),
        playback_key=media_item.get("audio_playback_key"),
        presigned_url=get_presigned_media_url(
            stream_key,
            content_type=content_type,
            download=download,
            filename=filename if download else None,
        ),
        stream_url=urls["stream_url"],
        download_url=urls["download_url"],
        content_type=content_type,
    )


@router.get("/voice/media", response_model=InterviewMediaPlaybackResponse)
def get_interview_answer_media(
    request: Request,
    user_id: int = Query(...),
    interview_id: int = Query(...),
    order: int = Query(..., ge=1),
    kind: str = Query("audio", pattern="^(audio|video)$"),
    download: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)
    submission = assignment.submission_data if isinstance(assignment.submission_data, dict) else {}
    media_item = find_answer_media(submission, order=order)
    if not media_item:
        raise HTTPException(status_code=404, detail="Answer media not found")

    if kind == "video" and not media_item.get("video_key"):
        raise HTTPException(status_code=404, detail="Answer video not found")
    if kind == "audio" and not media_item.get("audio_key"):
        raise HTTPException(status_code=404, detail="Answer audio not found")

    stream_key, content_type = resolve_stream_key(media_item, kind=kind)
    if not stream_key:
        raise HTTPException(status_code=404, detail="Answer media not found")

    source_key = media_item.get(f"{kind}_key")
    playback_key = media_item.get(f"{kind}_playback_key")
    filename = media_filename(order, kind, content_type)
    urls = _media_urls(request, user_id=subject_user_id, interview_id=interview_id, order=order, kind=kind)
    return InterviewMediaPlaybackResponse(
        order=order,
        kind=kind,
        media_key=str(source_key),
        playback_key=playback_key,
        presigned_url=get_presigned_media_url(
            stream_key,
            content_type=content_type,
            download=download,
            filename=filename if download else None,
        ),
        stream_url=urls["stream_url"],
        download_url=urls["download_url"],
        content_type=content_type,
    )


def _checkpoint_transcript(media_item: dict) -> str:
    for key in ("transcript", "answer"):
        value = (media_item.get(key) or "").strip()
        if value:
            return value
    return ""


def _load_answer_media_payload(
    *,
    db: Session,
    assignment,
    subject_user_id: int,
    interview_id: int,
    order: int,
    kind: str,
    media_item: dict,
    stream_key: str,
    content_type: str,
) -> tuple[bytes, str]:
    fallback_key = media_item.get("audio_key") if kind == "audio" else media_item.get("video_key")

    def _try_load(key: str) -> tuple[bytes, str]:
        return load_stream_bytes(key, kind=kind, content_type=content_type)

    try:
        return _try_load(stream_key)
    except FileNotFoundError:
        if fallback_key and str(fallback_key) != str(stream_key):
            return _try_load(str(fallback_key))
        raise
    except UnplayableMediaError:
        if kind != "audio":
            raise
        if fallback_key and str(fallback_key) != str(stream_key):
            try:
                return _try_load(str(fallback_key))
            except (FileNotFoundError, UnplayableMediaError):
                pass

        transcript = _checkpoint_transcript(media_item)
        if len(transcript) < 3:
            raise

        voice = resolve_assignment_voice_config(db, subject_user_id, interview_id)
        playback_text = transcript[:4000]
        mp3_bytes = synthesize_launch_speech(text=playback_text, voice=voice, db=db)
        if not mp3_bytes:
            raise UnplayableMediaError("Could not rebuild legacy answer audio")

        cached = cache_playback_mp3(
            mp3_bytes=mp3_bytes,
            user_id=subject_user_id,
            interview_id=interview_id,
            assignment_id=assignment.id,
            question_order=order,
            suffix="audio_playback_legacy",
        )
        update_answer_playback_cache(
            db,
            assignment,
            question_order=order,
            audio_playback_key=cached["playback_key"],
            audio_playback_url=cached["playback_url"],
        )
        logger.info(
            "Legacy answer audio rebuilt from transcript user=%s interview=%s order=%s key=%s",
            subject_user_id,
            interview_id,
            order,
            cached["playback_key"],
        )
        return mp3_bytes, "audio/mpeg"


@router.get("/voice/media/stream")
def stream_interview_answer_media(
    user_id: int = Query(...),
    interview_id: int = Query(...),
    order: int = Query(..., ge=1),
    kind: str = Query("audio", pattern="^(audio|video)$"),
    download: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authenticated stream proxy for answer audio/video (avoids S3 CORS issues)."""
    subject_user_id = resolve_interview_subject_user(
        db, current_user, user_id, interview_id, read_only=True,
    )
    assignment, _launch = get_user_assignment(db, subject_user_id, interview_id)
    submission = assignment.submission_data if isinstance(assignment.submission_data, dict) else {}
    media_item = find_answer_media(submission, order=order)
    if not media_item:
        raise HTTPException(status_code=404, detail="Answer media not found")

    stream_key, content_type = resolve_stream_key(media_item, kind=kind)
    if not stream_key:
        raise HTTPException(status_code=404, detail="Answer media not found")

    try:
        payload, served_type = _load_answer_media_payload(
            db=db,
            assignment=assignment,
            subject_user_id=subject_user_id,
            interview_id=interview_id,
            order=order,
            kind=kind,
            media_item=media_item,
            stream_key=str(stream_key),
            content_type=content_type,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Media file not found") from exc
    except UnplayableMediaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    headers = {"Accept-Ranges": "bytes", "Content-Length": str(len(payload))}
    if download:
        filename = media_filename(order, kind, served_type)
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return Response(content=payload, media_type=served_type, headers=headers)
