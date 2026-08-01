"""Private, local-first Music Lab analysis for uncompressed WAV audio.

This intentionally starts with a small DSP engine instead of downloading a large
source-separation model.  It can estimate timing, harmonic content and a melody
outline on modest hardware, then exports editable MIDI, chord text and guitar TAB.
Results are labelled as estimates; a mixture cannot be perfectly separated without
an additional stem model such as Demucs.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import BoundedSemaphore
from typing import Any, TYPE_CHECKING
from uuid import uuid4
import wave
import xml.etree.ElementTree as ElementTree
import zipfile

import numpy as np
from PIL import Image
from pypdf import PdfReader

from app.core.settings import settings
from app.services.resource_service import ResourceService

if TYPE_CHECKING:
    from app.services.auth_service import AuthenticatedUser


class MusicError(ValueError):
    """A safe Music Lab error suitable for the authenticated UI."""


class MusicService:
    _slot = BoundedSemaphore(1)
    _music_id_pattern = re.compile(r"^[a-f0-9]{32}$")
    _max_upload_bytes = 80 * 1024 * 1024
    _max_pdf_bytes = 20 * 1024 * 1024
    _max_duration_seconds = 6 * 60
    _retention_per_user = 12
    _pitch_names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    _artifact_names = {
        "midi": ("arrangement.mid", "audio/midi", "mycodex-music.mid"),
        "chords": ("chords.txt", "text/plain; charset=utf-8", "mycodex-chords.txt"),
        "tab": ("guitar-tab.txt", "text/plain; charset=utf-8", "mycodex-guitar-tab.txt"),
        "analysis": ("analysis.json", "application/json", "mycodex-analysis.json"),
    }
    _sampled_instruments = {
        "piano": (0, "Acoustic Grand Piano"),
        "guitar": (25, "Acoustic Guitar (steel)"),
        "bass": (33, "Electric Bass (finger)"),
        "strings": (48, "String Ensemble"),
        "flute": (73, "Flute"),
    }

    @classmethod
    def status(cls) -> dict[str, object]:
        omr_available = bool(cls._omr_executable())
        tab_ocr_available = bool(cls._tab_ocr_executable())
        sample_playback_available = cls._sample_engine_paths() is not None
        return {
            "configured": True,
            "engine": "MyCodex Local Music DSP + PDF TAB reader/OCR",
            "supported_formats": ["WAV (PCM)", "PDF chord sheet / vector TAB", "scanned score PDF when OMR is enabled", "MIDI / TXT output"],
            "separation_available": False,
            "omr_available": omr_available,
            "tab_ocr_available": tab_ocr_available,
            "sample_playback_available": sample_playback_available,
            "detail": "อ่านคอร์ดจาก PDF และอ่านสาย/เฟรตจาก PDF TAB แบบเวกเตอร์ได้ · OMR สำหรับ PDF สแกน " + ("พร้อมใช้งาน" if omr_available else "ยังไม่ได้ติดตั้งในเครื่อง") + " · เสียง sampled " + ("พร้อมใช้งาน" if sample_playback_available else "ยังไม่พร้อม"),
        }

    @classmethod
    def create(cls, user: AuthenticatedUser, filename: str, content: bytes) -> dict[str, object]:
        clean_name = cls._clean_filename(filename)
        if not content:
            raise MusicError("กรุณาเลือกไฟล์เพลง WAV หรือ PDF โน้ตเพลง")
        if len(content) > cls._max_upload_bytes:
            raise MusicError("ไฟล์เพลงมีขนาดเกิน 80 MB")
        suffix = Path(clean_name).suffix.casefold()
        if suffix == ".pdf":
            return cls._create_pdf_sheet(user, clean_name, content)
        if suffix not in {".wav", ".wave"}:
            raise MusicError("รุ่นนี้รองรับไฟล์ WAV (PCM) และ PDF chord sheet")

        duration = cls._validate_wav(content)
        music_id = uuid4().hex
        directory = cls._track_directory(user.id, music_id)
        metadata = {
            "music_id": music_id,
            "kind": "audio",
            "file_name": clean_name,
            "bytes": len(content),
            "duration_seconds": round(duration, 3),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "audio.wav").write_bytes(content)
            cls._write_json(directory / "meta.json", metadata)
            cls._trim_history(user.id)
        except OSError as error:
            raise MusicError("ไม่สามารถบันทึกไฟล์เพลงลงในเครื่องได้") from error
        return cls._track_response(metadata)

    @classmethod
    def _create_pdf_sheet(cls, user: AuthenticatedUser, clean_name: str, content: bytes) -> dict[str, object]:
        if len(content) > cls._max_pdf_bytes:
            raise MusicError("ไฟล์ PDF มีขนาดเกิน 20 MB")
        pages, extracted = cls._validate_pdf(content)
        music_id = uuid4().hex
        directory = cls._track_directory(user.id, music_id)
        metadata = {
            "music_id": music_id,
            "kind": "sheet",
            "file_name": clean_name,
            "bytes": len(content),
            "duration_seconds": None,
            "page_count": pages,
            "text_characters": len(extracted),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "sheet.pdf").write_bytes(content)
            cls._write_json(directory / "meta.json", metadata)
            cls._trim_history(user.id)
        except OSError as error:
            raise MusicError("ไม่สามารถบันทึก PDF โน้ตเพลงลงในเครื่องได้") from error
        return cls._track_response(metadata)

    @classmethod
    def list_for(cls, user: AuthenticatedUser) -> list[dict[str, object]]:
        tracks: list[dict[str, object]] = []
        directory = cls._owner_directory(user.id)
        try:
            children = list(directory.iterdir())
        except OSError:
            return []
        for item in children:
            if not item.is_dir() or not cls._music_id_pattern.fullmatch(item.name):
                continue
            metadata = cls._read_json(item / "meta.json")
            if metadata:
                tracks.append(cls._track_response(metadata, analyzed=(item / "analysis.json").is_file()))
        return sorted(tracks, key=lambda track: str(track["created_at"]), reverse=True)[: cls._retention_per_user]

    @classmethod
    def analyze(cls, user: AuthenticatedUser, music_id: str) -> dict[str, Any]:
        directory = cls._track_directory(user.id, music_id)
        metadata = cls._read_json(directory / "meta.json")
        source = directory / "audio.wav"
        sheet = directory / "sheet.pdf"
        if not metadata or (metadata.get("kind") == "sheet" and not sheet.is_file()) or (metadata.get("kind") != "sheet" and not source.is_file()):
            raise MusicError("ไม่พบไฟล์เพลงที่ร้องขอ")

        try:
            with cls._slot:
                if metadata.get("kind") == "sheet":
                    analysis = cls._analyze_pdf_sheet(directory / "sheet.pdf")
                else:
                    samples, sample_rate, duration = cls._load_wav(source)
                    analysis = cls._analyze_samples(samples, sample_rate, duration)
                cls._write_outputs(directory, analysis)
                analysis["artifacts"] = cls._artifact_urls(music_id)
                cls._write_json(directory / "analysis.json", analysis)
        except MusicError:
            raise
        except (OSError, ValueError, wave.Error) as error:
            raise MusicError("ไม่สามารถวิเคราะห์ไฟล์เสียงนี้ได้") from error
        return analysis

    @classmethod
    def analysis_for(cls, user: AuthenticatedUser, music_id: str) -> dict[str, Any]:
        directory = cls._track_directory(user.id, music_id)
        analysis = cls._read_json(directory / "analysis.json")
        if not analysis:
            raise MusicError("เพลงนี้ยังไม่ได้วิเคราะห์")
        analysis["artifacts"] = cls._artifact_urls(music_id)
        return analysis

    @classmethod
    def audio_path_for(cls, user: AuthenticatedUser, music_id: str) -> Path:
        metadata = cls._read_json(cls._track_directory(user.id, music_id) / "meta.json")
        if metadata.get("kind") != "audio":
            raise MusicError("รายการนี้เป็น PDF โน้ตเพลง ไม่มีไฟล์เสียงต้นฉบับ")
        path = cls._track_directory(user.id, music_id) / "audio.wav"
        if not path.is_file():
            raise MusicError("ไม่พบไฟล์เพลงที่ร้องขอ")
        return path

    @classmethod
    def source_path_for(cls, user: AuthenticatedUser, music_id: str) -> tuple[Path, str, str]:
        directory = cls._track_directory(user.id, music_id)
        metadata = cls._read_json(directory / "meta.json")
        if metadata.get("kind") == "sheet":
            path = directory / "sheet.pdf"
            if path.is_file():
                return path, "application/pdf", "sheet.pdf"
        return cls.audio_path_for(user, music_id), "audio/wav", "source.wav"

    @classmethod
    def artifact_for(cls, user: AuthenticatedUser, music_id: str, artifact: str) -> tuple[Path, str, str]:
        configured = cls._artifact_names.get(artifact)
        if configured is None:
            raise MusicError("ไม่พบไฟล์ส่งออกที่ร้องขอ")
        name, media_type, download_name = configured
        path = cls._track_directory(user.id, music_id) / name
        if not path.is_file():
            raise MusicError("กรุณาวิเคราะห์เพลงก่อนดาวน์โหลดไฟล์นี้")
        return path, media_type, download_name

    @classmethod
    def render_sampled(cls, user: AuthenticatedUser, music_id: str, instrument: str) -> dict[str, object]:
        configured = cls._sampled_instruments.get(instrument)
        if configured is None:
            raise MusicError("ไม่รู้จักเครื่องดนตรีที่เลือก")
        engine = cls._sample_engine_paths()
        if engine is None:
            raise MusicError("ยังไม่พบเอนจินเสียง sampled หรือ SoundFont ในเครื่องนี้")
        directory = cls._track_directory(user.id, music_id)
        analysis = cls._read_json(directory / "analysis.json")
        notes = analysis.get("notes") if analysis else None
        if not isinstance(notes, list) or not notes:
            raise MusicError("กรุณาวิเคราะห์เพลงก่อนเล่นด้วยเสียง sampled")
        capacity = ResourceService.snapshot()
        available_mb = capacity.get("available_memory_mb")
        if isinstance(available_mb, int) and available_mb < settings.music_render_min_available_mb:
            raise MusicError(
                f"หน่วยความจำว่าง {available_mb} MB ยังไม่พอสำหรับการเรนเดอร์เสียงคุณภาพสูง "
                f"(ต้องมีอย่างน้อย {settings.music_render_min_available_mb} MB)"
            )
        output = directory / f"render-{instrument}.wav"
        if output.is_file() and output.stat().st_size > 4_096:
            return {"instrument": instrument, "label": configured[1], "cached": True}

        executable, soundfont = engine
        render_midi = directory / f"render-{instrument}.mid"
        tempo = float((analysis.get("tempo") or {}).get("bpm") or 120)
        try:
            render_midi.write_bytes(cls._midi_bytes(notes, tempo, program=configured[0]))
            with cls._slot:
                completed = subprocess.run(
                    [
                        str(executable), "-ni", "-F", str(output), "-r", "48000", "-g", "0.55",
                        "-o", "synth.polyphony=64",
                        "-o", "synth.reverb.active=1", "-o", "synth.chorus.active=1",
                        str(soundfont), str(render_midi),
                    ],
                    cwd=str(directory),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=settings.music_render_timeout_seconds,
                    check=False,
                    shell=False,
                )
        except (OSError, subprocess.SubprocessError) as error:
            raise MusicError("ไม่สามารถเริ่มเอนจินเสียง sampled ได้") from error
        if completed.returncode != 0 or not output.is_file() or output.stat().st_size <= 4_096:
            raise MusicError("สร้างเสียง sampled ไม่สำเร็จ โปรดลองใหม่")
        return {"instrument": instrument, "label": configured[1], "cached": False}

    @classmethod
    def sampled_audio_path_for(cls, user: AuthenticatedUser, music_id: str, instrument: str) -> Path:
        if instrument not in cls._sampled_instruments:
            raise MusicError("ไม่รู้จักเครื่องดนตรีที่เลือก")
        path = cls._track_directory(user.id, music_id) / f"render-{instrument}.wav"
        if not path.is_file() or path.stat().st_size <= 4_096:
            raise MusicError("ยังไม่มีเสียง sampled สำหรับเครื่องดนตรีนี้")
        return path

    @classmethod
    def _validate_wav(cls, content: bytes) -> float:
        try:
            with wave.open(BytesIO(content), "rb") as audio:
                if audio.getcomptype() != "NONE":
                    raise MusicError("รองรับ WAV แบบ PCM ที่ไม่บีบอัดเท่านั้น")
                if audio.getsampwidth() not in {1, 2, 3, 4} or audio.getnchannels() < 1:
                    raise MusicError("รูปแบบเสียง WAV นี้ไม่รองรับ")
                if audio.getframerate() < 4_000:
                    raise MusicError("อัตราสุ่มตัวอย่างเสียงต่ำเกินไป")
                duration = audio.getnframes() / float(audio.getframerate())
        except wave.Error as error:
            raise MusicError("ไฟล์นี้ไม่ใช่ WAV PCM ที่อ่านได้") from error
        if duration <= 1:
            raise MusicError("ไฟล์เสียงสั้นเกินไปสำหรับการวิเคราะห์")
        if duration > cls._max_duration_seconds:
            raise MusicError("เพลงยาวเกิน 6 นาทีสำหรับการวิเคราะห์บนเครื่องนี้")
        return duration

    @classmethod
    def _validate_pdf(cls, content: bytes) -> tuple[int, str]:
        try:
            reader = PdfReader(BytesIO(content))
            if not reader.pages or len(reader.pages) > 80:
                raise MusicError("PDF ต้องมี 1-80 หน้า")
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        except MusicError:
            raise
        except Exception as error:
            raise MusicError("ไม่สามารถอ่าน PDF นี้ได้") from error
        # Image-only PDFs are still safe to store.  Analysis will use the
        # optional OMR bridge when it is configured, rather than rejecting a
        # score before the user gets a chance to read it.
        clean_text = " ".join(extracted.split())
        return len(reader.pages), clean_text[:200_000]

    @classmethod
    def _load_wav(cls, source: Path) -> tuple[np.ndarray, int, float]:
        with wave.open(str(source), "rb") as audio:
            sample_rate = audio.getframerate()
            channels = audio.getnchannels()
            width = audio.getsampwidth()
            frames = audio.getnframes()
            duration = frames / float(sample_rate)
            if audio.getcomptype() != "NONE" or width not in {1, 2, 3, 4}:
                raise MusicError("รูปแบบเสียง WAV นี้ไม่รองรับ")
            raw = audio.readframes(frames)

        if width == 1:
            values = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif width == 2:
            values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif width == 3:
            packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
            values = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
            values = ((values ^ (1 << 23)) - (1 << 23)).astype(np.float32) / float(1 << 23)
        else:
            values = np.frombuffer(raw, dtype="<i4").astype(np.float32) / float(1 << 31)
        if values.size < channels:
            raise MusicError("ไม่พบข้อมูลเสียงสำหรับวิเคราะห์")
        mono = values[: values.size - (values.size % channels)].reshape(-1, channels).mean(axis=1)
        # Keep analysis memory and CPU bounded on an 8 GB PC.  This does not
        # change the source audio or downloaded WAV file.
        stride = max(1, int(math.ceil(sample_rate / 11_025)))
        return np.ascontiguousarray(mono[::stride], dtype=np.float32), max(1, sample_rate // stride), duration

    @classmethod
    def _analyze_samples(cls, samples: np.ndarray, sample_rate: int, duration: float) -> dict[str, Any]:
        hop = 512
        envelope = cls._onset_envelope(samples, hop)
        bpm, confidence = cls._estimate_tempo(envelope, sample_rate, hop)
        beats = cls._beat_times(envelope, sample_rate, hop, bpm, duration)
        chords, profile = cls._estimate_chords(samples, sample_rate, bpm, duration)
        key_name = cls._estimate_key(profile)
        notes = cls._estimate_melody(samples, sample_rate, beats)
        parts = cls._estimate_parts(samples, sample_rate, envelope)
        groove = "straight" if confidence >= 0.28 else "free / unclear"
        return {
            "engine": "MyCodex Local Music DSP · beta",
            "limitations": [
                "คอร์ด โน้ต และจังหวะเป็นค่าประมาณจากเพลงมิกซ์รวม ควรฟังตรวจทานก่อนใช้งานจริง",
                "รุ่นนี้ยังไม่แยกเสียงร้อง กลอง เบส และเครื่องดนตรีเป็นไฟล์ stem แยกกัน",
            ],
            "audio": {"duration_seconds": round(duration, 2), "analysis_sample_rate": sample_rate},
            "tempo": {"bpm": round(bpm, 1), "confidence": round(confidence, 2)},
            "rhythm": {"meter": "4/4 (estimated)", "groove": groove, "beat_count": len(beats)},
            "key": {"name": key_name, "confidence": "estimated"},
            "chords": chords,
            "notes": notes,
            "detected_parts": parts,
            "stem_separation": {
                "available": False,
                "detail": "ยังไม่ติดตั้ง stem model เพื่อไม่ให้เครื่อง 8 GB หนักเกินไป",
            },
        }

    @classmethod
    def _analyze_pdf_sheet(cls, source: Path) -> dict[str, Any]:
        try:
            reader = PdfReader(str(source))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as error:
            raise MusicError("ไม่สามารถอ่านข้อความจาก PDF ได้") from error
        bpm_match = re.search(r"(?:tempo|bpm|q\s*=|=)\s*[:=]?\s*(\d{2,3})", text, re.IGNORECASE)
        bpm = float(np.clip(int(bpm_match.group(1)) if bpm_match else 120, 40, 240))
        tablature = cls._extract_vector_tablature(reader, bpm)
        if tablature["notes"]:
            return cls._analysis_from_tablature(tablature, bpm, len(reader.pages), bool(bpm_match))
        raster_tablature = cls._extract_raster_tablature(reader, bpm)
        if raster_tablature["notes"]:
            return cls._analysis_from_tablature(raster_tablature, bpm, len(reader.pages), bool(bpm_match))

        chords = cls._chords_from_text(text)
        if not chords:
            return cls._analyze_with_omr(source, len(reader.pages))
        meter_match = re.search(r"\b([2-9]|1[0-2])\s*/\s*([2-9]|1[0-6])\b", text)
        meter = f"{meter_match.group(1)}/{meter_match.group(2)} (from PDF)" if meter_match else "4/4 (assumed)"
        bar_seconds = 4 * 60.0 / bpm
        chord_events = [
            {"start": round(index * bar_seconds, 2), "end": round((index + 1) * bar_seconds, 2), "name": chord, "confidence": 1.0}
            for index, chord in enumerate(chords[:128])
        ]
        profile = cls._profile_from_chords(chords)
        notes = cls._notes_from_chords(chord_events, bpm)
        return {
            "engine": "MyCodex PDF chord-sheet reader · beta",
            "limitations": [
                "อ่านคอร์ดและ tempo จากข้อความที่ฝังใน PDF ไม่ใช่การอ่านโน้ตห้าเส้นจากภาพ",
                "หาก PDF เป็นภาพสแกน ให้ใช้ไฟล์ที่เลือกข้อความได้ หรือเพิ่มระบบ OMR ภายหลัง",
            ],
            "audio": {"page_count": len(reader.pages), "source": "PDF text sheet"},
            "tempo": {"bpm": bpm, "confidence": 1.0 if bpm_match else 0.35},
            "rhythm": {"meter": meter, "groove": "from chord sheet", "beat_count": len(chords) * 4},
            "key": {"name": cls._estimate_key(profile), "confidence": "estimated from chord symbols"},
            "chords": chord_events,
            "notes": notes,
            "detected_parts": [{"name": "PDF chord sheet", "confidence": "text extracted", "detail": "พบคอร์ดจากข้อความใน PDF"}],
            "stem_separation": {"available": False, "detail": "PDF ไม่มีเสียงต้นฉบับสำหรับแยก stem"},
        }

    @classmethod
    def _extract_vector_tablature(cls, reader: PdfReader, bpm: float) -> dict[str, Any]:
        """Read selectable fret glyphs positioned on 4- or 6-line TAB systems.

        Music notation exported from Sibelius and similar editors often preserves
        each fret as a positioned text glyph.  Reading those coordinates is more
        reliable than image OCR and retains the actual string for playback.
        """
        systems: list[tuple[list[float], list[dict[str, Any]]]] = []
        for page in reader.pages:
            glyphs: list[dict[str, Any]] = []

            def visitor(text: str, _cm: Any, tm: Any, _font: Any, size: float) -> None:
                token = text.strip()
                if (
                    re.fullmatch(r"(?:\d{1,2}|[xX])", token)
                    and 45 <= float(size or 0) <= 70
                    and float(tm[4]) > 200
                    and float(tm[5]) > 200
                ):
                    glyphs.append({"token": token, "x": float(tm[4]), "y": float(tm[5])})

            page.extract_text(visitor_text=visitor)
            systems.extend(cls._tab_systems_from_glyphs(glyphs))

        return cls._tablature_from_systems(systems, bpm, source="vector")

    @classmethod
    def _extract_raster_tablature(cls, reader: PdfReader, bpm: float) -> dict[str, Any]:
        """Read string rows and OCR fret numbers from image-only TAB pages."""
        executable = cls._tab_ocr_executable()
        if not executable:
            return cls._tablature_from_systems([], bpm, source="scan_ocr")
        systems: list[tuple[list[float], list[dict[str, Any]]]] = []
        with tempfile.TemporaryDirectory(prefix="mycodex-tab-ocr-") as temporary:
            for page_index, page in enumerate(reader.pages[:80]):
                try:
                    images = [item.image for item in page.images]
                except Exception:
                    continue
                if not images:
                    continue
                image = max(images, key=lambda item: int(item.width) * int(item.height)).convert("L")
                row_groups, grayscale = cls._tab_rows_from_image(image)
                if not row_groups:
                    continue
                glyphs = cls._ocr_raster_tab_glyphs(
                    grayscale,
                    row_groups,
                    executable,
                    Path(temporary) / f"page-{page_index}.png",
                )
                for rows in row_groups:
                    gap = float(np.median(np.diff(rows))) if len(rows) > 1 else 20.0
                    tolerance = max(7.0, gap * 0.48)
                    items = [item for item in glyphs if min(abs(float(item["y"]) - row) for row in rows) <= tolerance]
                    if len(items) >= 4:
                        systems.append((rows, items))
        return cls._tablature_from_systems(systems, bpm, source="scan_ocr")

    @staticmethod
    def _tab_rows_from_image(image: Image.Image) -> tuple[list[list[float]], np.ndarray]:
        grayscale = np.asarray(image.convert("L"), dtype=np.uint8)
        if grayscale.ndim != 2 or grayscale.shape[0] < 100 or grayscale.shape[1] < 100:
            return [], grayscale
        dark = grayscale < 170
        minimum_ink = max(80, int(grayscale.shape[1] * 0.25))
        candidates = np.flatnonzero(np.count_nonzero(dark, axis=1) >= minimum_ink)
        centers: list[float] = []
        group: list[int] = []
        for value in candidates.tolist():
            if group and value > group[-1] + 1:
                centers.append(float(np.mean(group)))
                group = []
            group.append(value)
        if group:
            centers.append(float(np.mean(group)))

        systems: list[list[float]] = []
        index = 0
        while index < len(centers):
            matched: list[float] | None = None
            for count in (6, 4):
                rows = centers[index:index + count]
                if len(rows) != count:
                    continue
                gaps = np.diff(rows)
                median = float(np.median(gaps))
                if 6.0 <= median <= 90.0 and float(np.max(np.abs(gaps - median))) <= max(2.5, median * 0.22):
                    matched = rows
                    break
            if matched:
                systems.append(matched)
                index += len(matched)
            else:
                index += 1
        return systems, grayscale

    @staticmethod
    def _ocr_raster_tab_glyphs(
        grayscale: np.ndarray,
        row_groups: list[list[float]],
        executable: str,
        image_path: Path,
    ) -> list[dict[str, Any]]:
        prepared = np.where(grayscale < 190, 0, 255).astype(np.uint8)
        for row in (value for rows in row_groups for value in rows):
            center = int(round(row))
            prepared[max(0, center - 1):min(prepared.shape[0], center + 2), :] = 255
        Image.fromarray(prepared, mode="L").save(image_path, format="PNG")
        try:
            completed = subprocess.run(
                [executable, str(image_path), "stdout", "--psm", "11", "-c", "tessedit_char_whitelist=0123456789xX", "tsv"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.music_tab_ocr_timeout_seconds,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if completed.returncode != 0:
            return []
        glyphs: list[dict[str, Any]] = []
        for row in csv.DictReader(completed.stdout.splitlines(), delimiter="\t"):
            token = str(row.get("text") or "").strip()
            try:
                confidence = float(row.get("conf") or -1)
                left = float(row.get("left") or 0)
                top = float(row.get("top") or 0)
                width = float(row.get("width") or 0)
                height = float(row.get("height") or 0)
            except (TypeError, ValueError):
                continue
            if confidence < 20 or not re.fullmatch(r"(?:\d{1,2}|[xX])", token):
                continue
            glyphs.append({"token": token, "x": left + width / 2.0, "y": top + height / 2.0})
        return glyphs

    @classmethod
    def _tablature_from_systems(
        cls,
        systems: list[tuple[list[float], list[dict[str, Any]]]],
        bpm: float,
        *,
        source: str = "vector",
    ) -> dict[str, Any]:
        if not systems:
            return {"instrument": "Unknown", "tuning": [], "notes": [], "events": [], "string_count": 0, "source": source}
        common_count = max((len(rows) for rows, _items in systems), key=lambda count: sum(len(rows) == count for rows, _ in systems))
        tuning = cls._tab_tuning(common_count)
        if not tuning:
            return {"instrument": "Unknown", "tuning": [], "notes": [], "events": [], "string_count": 0}

        beat_seconds = 60.0 / bpm
        notes: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        system_index = 0
        for rows, glyphs in systems:
            if len(rows) != common_count:
                continue
            numeric = [item for item in glyphs if item["token"].casefold() != "x"]
            if not numeric:
                system_index += 1
                continue
            minimum = min(float(item["x"]) for item in glyphs)
            maximum = max(float(item["x"]) for item in glyphs)
            span = max(1.0, maximum - minimum)
            for item in glyphs:
                row = min(range(len(rows)), key=lambda index: abs(float(item["y"]) - rows[index]))
                beat = system_index * 16 + ((float(item["x"]) - minimum) / span) * 16
                start = round(beat * beat_seconds, 3)
                string_name, open_midi = tuning[row]
                event = {"start": start, "string": string_name, "token": str(item["token"]), "fret": None, "muted": str(item["token"]).casefold() == "x"}
                if event["muted"]:
                    events.append(event)
                    continue
                fret = int(str(item["token"]))
                midi = open_midi + fret
                event["fret"] = fret
                events.append(event)
                notes.append({"start": start, "duration": round(beat_seconds * 0.58, 3), "midi": midi, "name": cls._midi_name(midi), "confidence": 1.0, "string": string_name, "fret": fret})
            system_index += 1
        return {
            "instrument": "4-string bass" if common_count == 4 else "6-string guitar",
            "tuning": [f"{name}{cls._midi_name(midi)[-1]}" for name, midi in tuning],
            "notes": sorted(notes, key=lambda note: (float(note["start"]), str(note["string"]))),
            "events": sorted(events, key=lambda event: (float(event["start"]), str(event["string"]))),
            "string_count": common_count,
            "source": source,
        }

    @staticmethod
    def _tab_ocr_executable() -> str | None:
        configured = settings.music_tab_ocr_executable.strip()
        if not configured:
            return None
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        return shutil.which(configured)

    @staticmethod
    def _tab_systems_from_glyphs(glyphs: list[dict[str, Any]]) -> list[tuple[list[float], list[dict[str, Any]]]]:
        if not glyphs:
            return []
        baselines: list[float] = []
        for value in sorted(float(item["y"]) for item in glyphs):
            if not baselines or value - baselines[-1] > 9:
                baselines.append(value)
            else:
                baselines[-1] = (baselines[-1] + value) / 2
        gaps = [later - earlier for earlier, later in zip(baselines, baselines[1:]) if 12 < later - earlier < 110]
        line_gap = float(np.median(gaps)) if gaps else 48.0
        row_groups: list[list[float]] = []
        for baseline in baselines:
            if not row_groups or baseline - row_groups[-1][-1] > line_gap * 1.8:
                row_groups.append([baseline])
            else:
                row_groups[-1].append(baseline)
        systems: list[tuple[list[float], list[dict[str, Any]]]] = []
        for rows in row_groups:
            if len(rows) not in {4, 6}:
                continue
            tolerance = max(14.0, line_gap * 0.36)
            items = [item for item in glyphs if min(abs(float(item["y"]) - row) for row in rows) <= tolerance]
            if len(items) >= 6:
                systems.append((rows, items))
        return systems

    @staticmethod
    def _tab_tuning(string_count: int) -> list[tuple[str, int]]:
        # TAB is drawn high string at the top and low string at the bottom.
        if string_count == 4:
            return [("G", 43), ("D", 38), ("A", 33), ("E", 28)]
        if string_count == 6:
            return [("e", 64), ("B", 59), ("G", 55), ("D", 50), ("A", 45), ("E", 40)]
        return []

    @staticmethod
    def _omr_executable() -> str | None:
        """Return only the administrator-configured OMR executable.

        Score PDFs never provide a command or path.  This prevents an uploaded
        document from influencing the program that is launched on the host.
        """
        configured = settings.music_omr_executable.strip()
        if not configured:
            return None
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        return shutil.which(configured)

    @staticmethod
    def _local_configured_path(value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (Path.cwd() / path)

    @classmethod
    def _sample_engine_paths(cls) -> tuple[Path, Path] | None:
        executable = cls._local_configured_path(settings.music_fluidsynth_executable)
        soundfont = cls._local_configured_path(settings.music_soundfont_path)
        if executable.is_file() and soundfont.is_file() and soundfont.stat().st_size > 1_000_000:
            return executable, soundfont
        return None

    @classmethod
    def _analyze_with_omr(cls, source: Path, pages: int) -> dict[str, Any]:
        executable = cls._omr_executable()
        if not executable:
            raise MusicError(
                "PDF นี้ไม่มีข้อความหรือ TAB ที่เลือกได้ จึงต้องใช้ OMR สำหรับโน้ตสแกน "
                "แต่เครื่องนี้ยังไม่ได้ตั้งค่า OMR"
            )

        output_directory = source.parent / "omr" / uuid4().hex
        output_directory.mkdir(parents=True, exist_ok=False)
        command = [
            executable,
            "-batch",
            "-transcribe",
            "-export",
            "-output",
            str(output_directory),
            "--",
            str(source),
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=settings.music_omr_timeout_seconds,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise MusicError("ไม่สามารถเริ่ม OMR ในเครื่องนี้ได้") from error
        if completed.returncode != 0:
            raise MusicError("OMR อ่านโน้ตจาก PDF นี้ไม่สำเร็จ กรุณาตรวจไฟล์ต้นฉบับแล้วลองใหม่")

        exports = sorted(
            [*output_directory.rglob("*.musicxml"), *output_directory.rglob("*.xml"), *output_directory.rglob("*.mxl")],
            key=lambda path: path.stat().st_size if path.is_file() else 0,
            reverse=True,
        )
        if not exports:
            raise MusicError("OMR ทำงานเสร็จ แต่ไม่พบไฟล์ MusicXML สำหรับอ่านโน้ต")
        return cls._analysis_from_musicxml(exports[0], pages)

    @staticmethod
    def _xml_name(element: ElementTree.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    @classmethod
    def _xml_child(cls, element: ElementTree.Element, name: str) -> ElementTree.Element | None:
        return next((child for child in element if cls._xml_name(child) == name), None)

    @classmethod
    def _xml_text(cls, element: ElementTree.Element, name: str, default: str = "") -> str:
        child = cls._xml_child(element, name)
        return (child.text or default).strip() if child is not None else default

    @classmethod
    def _musicxml_root(cls, source: Path) -> ElementTree.Element:
        try:
            if source.suffix.casefold() == ".mxl":
                with zipfile.ZipFile(source) as archive:
                    entry = next(
                        (name for name in archive.namelist() if name.casefold().endswith((".musicxml", ".xml")) and not name.startswith("META-INF/")),
                        None,
                    )
                    if not entry:
                        raise ValueError("No MusicXML entry")
                    return ElementTree.fromstring(archive.read(entry))
            return ElementTree.parse(source).getroot()
        except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as error:
            raise MusicError("OMR สร้าง MusicXML ที่อ่านไม่ได้") from error

    @classmethod
    def _analysis_from_musicxml(cls, source: Path, pages: int) -> dict[str, Any]:
        root = cls._musicxml_root(source)
        tempo = 120.0
        meter = "4/4 (from OMR)"
        for element in root.iter():
            name = cls._xml_name(element)
            if name == "sound" and element.attrib.get("tempo", "").replace(".", "", 1).isdigit():
                tempo = float(np.clip(float(element.attrib["tempo"]), 40, 240))
                break
            if name == "per-minute" and (element.text or "").strip().replace(".", "", 1).isdigit():
                tempo = float(np.clip(float((element.text or "").strip()), 40, 240))
                break

        parts = [element for element in root if cls._xml_name(element) == "part"]
        if not parts:
            raise MusicError("OMR ไม่พบแนวโน้ตที่นำมาเล่นได้")
        part = parts[0]
        divisions = 1.0
        cursor = 0.0
        notes: list[dict[str, Any]] = []
        pitch_offsets = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        for measure in (item for item in part if cls._xml_name(item) == "measure"):
            for item in measure:
                item_name = cls._xml_name(item)
                if item_name == "attributes":
                    divisions_text = cls._xml_text(item, "divisions")
                    if divisions_text.isdigit() and int(divisions_text) > 0:
                        divisions = float(int(divisions_text))
                    time = cls._xml_child(item, "time")
                    if time is not None:
                        beats, beat_type = cls._xml_text(time, "beats"), cls._xml_text(time, "beat-type")
                        if beats.isdigit() and beat_type.isdigit():
                            meter = f"{beats}/{beat_type} (from OMR)"
                    continue
                if item_name in {"backup", "forward"}:
                    duration_text = cls._xml_text(item, "duration", "0")
                    duration = float(duration_text) / divisions if duration_text.isdigit() else 0.0
                    cursor += -duration if item_name == "backup" else duration
                    continue
                if item_name != "note":
                    continue
                duration_text = cls._xml_text(item, "duration", "0")
                beats = float(duration_text) / divisions if duration_text.isdigit() else 0.0
                is_chord = cls._xml_child(item, "chord") is not None
                pitch = cls._xml_child(item, "pitch")
                if pitch is not None:
                    step = cls._xml_text(pitch, "step").upper()
                    octave_text = cls._xml_text(pitch, "octave")
                    alter_text = cls._xml_text(pitch, "alter", "0")
                    if step in pitch_offsets and octave_text.lstrip("-").isdigit() and alter_text.lstrip("-").isdigit():
                        midi = (int(octave_text) + 1) * 12 + pitch_offsets[step] + int(alter_text)
                        if 0 <= midi <= 127:
                            notes.append({
                                "start": round(cursor * 60.0 / tempo, 3),
                                "duration": round(max(0.08, beats * 60.0 / tempo), 3),
                                "midi": midi,
                                "name": cls._midi_name(midi),
                                "confidence": 0.78,
                            })
                if not is_chord:
                    cursor += beats
                if len(notes) >= 1_200:
                    break
            if len(notes) >= 1_200:
                break
        if not notes:
            raise MusicError("OMR ไม่พบโน้ตที่นำมาเล่นได้จาก PDF นี้")
        profile = np.zeros(12, dtype=np.float64)
        for note in notes:
            profile[int(note["midi"]) % 12] += 1
        return {
            "engine": "MyCodex local OMR (MusicXML)",
            "limitations": [
                "OMR อ่านโน้ตจากภาพสแกนเป็นค่าเริ่มต้น ควรตรวจทานคีย์ จังหวะ และโน้ตที่มีสัญลักษณ์ซ้อนก่อนใช้งานจริง",
                "ระบบอ่านแนวโน้ตแรกของสกอร์เพื่อให้เล่นและส่งออก MIDI ได้เร็วบนเครื่องนี้",
            ],
            "audio": {"page_count": pages, "source": "scanned PDF score via local OMR", "duration_seconds": round(cursor * 60.0 / tempo, 2)},
            "tempo": {"bpm": tempo, "confidence": 0.78},
            "rhythm": {"meter": meter, "groove": "from OMR score", "beat_count": round(cursor)},
            "key": {"name": cls._estimate_key(profile), "confidence": "estimated from OMR notes"},
            "chords": [],
            "notes": notes,
            "detected_parts": [{"name": "OMR score", "confidence": "image notation read", "detail": "อ่านโน้ตจาก PDF สแกนผ่าน OMR แล้ว"}],
            "stem_separation": {"available": False, "detail": "PDF โน้ตไม่มีเสียงต้นฉบับสำหรับแยก stem"},
        }

    @classmethod
    def _analysis_from_tablature(cls, tablature: dict[str, Any], bpm: float, pages: int, tempo_found: bool) -> dict[str, Any]:
        notes = tablature["notes"]
        scanned = tablature.get("source") == "scan_ocr"
        duration = max((float(note["start"]) + float(note["duration"]) for note in notes), default=0.0)
        pitch_profile = np.zeros(12, dtype=np.float64)
        for note in notes:
            pitch_profile[int(note["midi"]) % 12] += 1
        return {
            "engine": "MyCodex PDF scanned TAB OCR" if scanned else "MyCodex PDF vector TAB reader",
            "limitations": [
                "อ่านตัวเลข fret และตำแหน่งสายจาก PDF TAB แบบเวกเตอร์; เทคนิคสไลด์/ฮัมเมอร์/จังหวะละเอียดอาจต้องตรวจทาน",
                "PDF สแกนเป็นรูปและโน้ตห้าเส้นที่ไม่มี TAB ยังต้องใช้ OMR engine เพิ่ม",
            ],
            "audio": {"page_count": pages, "source": "PDF vector TAB", "duration_seconds": round(duration, 2)},
            "tempo": {"bpm": bpm, "confidence": 1.0 if tempo_found else 0.35},
            "rhythm": {"meter": "4/4 (assumed from TAB layout)", "groove": "from TAB positions", "beat_count": round(duration / max(0.01, 60 / bpm))},
            "key": {"name": cls._estimate_key(pitch_profile), "confidence": "estimated from TAB pitches"},
            "chords": [],
            "notes": notes,
            "tablature": {key: value for key, value in tablature.items() if key != "notes"},
            "detected_parts": [{
                "name": str(tablature["instrument"]),
                "confidence": "OCR string/fret estimate" if scanned else "exact string/fret read",
                "detail": "ตรวจเส้นสายและอ่านเลขเฟรตจากภาพ TAB ด้วย OCR" if scanned else "อ่านสายและเฟรตจาก PDF TAB โดยตรง",
            }],
            "stem_separation": {"available": False, "detail": "PDF TAB ไม่มีไฟล์เสียงต้นฉบับสำหรับแยก stem"},
        }

    @classmethod
    def _chords_from_text(cls, text: str) -> list[str]:
        pattern = re.compile(r"(?<![A-Za-z])([A-G](?:#|b)?(?:maj7?|m(?:aj7|7|9)?|sus[24]|dim|aug|add9|[579]|6)?(?:/[A-G](?:#|b)?)?)(?![A-Za-z])")
        chords: list[str] = []
        for match in pattern.finditer(text):
            chord = cls._normalize_chord_name(match.group(1))
            if chord:
                chords.append(chord)
        return chords

    @classmethod
    def _normalize_chord_name(cls, chord: str) -> str:
        match = re.fullmatch(r"([A-G])([#b]?)(.*)", chord)
        if not match:
            return ""
        root = match.group(1) + match.group(2)
        flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B", "Fb": "E"}
        return flats.get(root, root) + match.group(3)

    @classmethod
    def _profile_from_chords(cls, chords: list[str]) -> np.ndarray:
        profile = np.zeros(12, dtype=np.float64)
        for chord in chords:
            root, minor = cls._chord_root(chord)
            if root is None:
                continue
            profile[root] += 1.1
            profile[(root + (3 if minor else 4)) % 12] += 0.85
            profile[(root + 7) % 12] += 0.8
        return profile

    @classmethod
    def _notes_from_chords(cls, chords: list[dict[str, Any]], bpm: float) -> list[dict[str, Any]]:
        notes: list[dict[str, Any]] = []
        for chord in chords:
            root, minor = cls._chord_root(str(chord["name"]))
            if root is None:
                continue
            start, duration = float(chord["start"]), float(chord["end"]) - float(chord["start"])
            triad = (48 + root, 48 + root + (3 if minor else 4), 48 + root + 7)
            for offset, midi in enumerate(triad):
                notes.append({
                    "start": round(start + (duration / 3) * offset, 3),
                    "duration": round(max(0.12, duration / 3 * 0.8), 3),
                    "midi": midi,
                    "name": cls._midi_name(midi),
                    "confidence": 1.0,
                })
        return notes[:192]

    @classmethod
    def _chord_root(cls, chord: str) -> tuple[int | None, bool]:
        match = re.match(r"([A-G](?:#|b)?)(.*)", chord)
        if not match:
            return None, False
        root = cls._normalize_chord_name(match.group(1))
        try:
            index = cls._pitch_names.index(root)
        except ValueError:
            return None, False
        suffix = match.group(2).casefold()
        return index, suffix.startswith("m") and not suffix.startswith("maj")

    @staticmethod
    def _onset_envelope(samples: np.ndarray, hop: int) -> np.ndarray:
        frame = hop * 2
        usable = len(samples) - (len(samples) % frame)
        if usable < frame * 3:
            return np.ones(8, dtype=np.float32)
        frames = samples[:usable].reshape(-1, frame)
        energy = np.sqrt(np.mean(np.square(frames), axis=1))
        onset = np.maximum(0.0, np.diff(energy, prepend=energy[0]))
        peak = float(np.max(onset))
        return onset / peak if peak > 1e-8 else np.ones_like(onset)

    @staticmethod
    def _estimate_tempo(envelope: np.ndarray, sample_rate: int, hop: int) -> tuple[float, float]:
        if len(envelope) < 12:
            return 120.0, 0.0
        scores: list[tuple[float, float]] = []
        for bpm in range(60, 201):
            lag = max(1, int(round((60.0 * sample_rate) / (bpm * hop))))
            if lag >= len(envelope):
                continue
            score = float(np.dot(envelope[lag:], envelope[:-lag])) / max(1, len(envelope) - lag)
            scores.append((score, float(bpm)))
        if not scores:
            return 120.0, 0.0
        scores.sort(reverse=True)
        best, bpm = scores[0]
        baseline = float(np.median([score for score, _ in scores])) or 1e-7
        return bpm, min(1.0, best / baseline / 4.0)

    @staticmethod
    def _beat_times(envelope: np.ndarray, sample_rate: int, hop: int, bpm: float, duration: float) -> list[float]:
        interval = 60.0 / max(1.0, bpm)
        period = max(1, int(round(interval * sample_rate / hop)))
        candidates = range(min(period, len(envelope)))
        phase = max(candidates, key=lambda offset: float(np.sum(envelope[offset::period])), default=0)
        start = phase * hop / sample_rate
        return [round(float(time), 3) for time in np.arange(start, max(start + interval, duration), interval) if time < duration]

    @classmethod
    def _estimate_chords(cls, samples: np.ndarray, sample_rate: int, bpm: float, duration: float) -> tuple[list[dict[str, Any]], np.ndarray]:
        bar = (60.0 / max(1.0, bpm)) * 4.0
        positions = np.arange(bar / 2.0, duration, bar)
        aggregate = np.zeros(12, dtype=np.float64)
        raw: list[dict[str, Any]] = []
        for position in positions:
            profile = cls._pitch_profile(samples, sample_rate, float(position))
            aggregate += profile
            name, score = cls._match_chord(profile)
            raw.append({"start": round(float(max(0, position - bar / 2.0)), 2), "end": round(float(min(duration, position + bar / 2.0)), 2), "name": name, "confidence": round(score, 2)})
        if not raw:
            raw = [{"start": 0.0, "end": round(duration, 2), "name": "N.C.", "confidence": 0.0}]
        merged: list[dict[str, Any]] = []
        for chord in raw:
            if merged and chord["name"] == merged[-1]["name"]:
                merged[-1]["end"] = chord["end"]
                merged[-1]["confidence"] = round((float(merged[-1]["confidence"]) + float(chord["confidence"])) / 2, 2)
            else:
                merged.append(chord)
        return merged, aggregate

    @staticmethod
    def _pitch_profile(samples: np.ndarray, sample_rate: int, center_seconds: float) -> np.ndarray:
        size = 4096
        center = int(center_seconds * sample_rate)
        start = max(0, center - size // 2)
        frame = samples[start : start + size]
        if len(frame) < size:
            frame = np.pad(frame, (0, size - len(frame)))
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(size)))
        frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate)
        mask = (frequencies >= 55.0) & (frequencies <= 1_500.0)
        frequencies, spectrum = frequencies[mask], spectrum[mask]
        profile = np.zeros(12, dtype=np.float64)
        if not len(frequencies):
            return profile
        midi = np.rint(69 + 12 * np.log2(frequencies / 440.0)).astype(int)
        np.add.at(profile, np.mod(midi, 12), np.sqrt(spectrum))
        return profile

    @classmethod
    def _match_chord(cls, profile: np.ndarray) -> tuple[str, float]:
        total = float(np.sum(profile))
        if total <= 1e-8:
            return "N.C.", 0.0
        candidates: list[tuple[float, str]] = []
        for root, name in enumerate(cls._pitch_names):
            major = profile[root] * 1.1 + profile[(root + 4) % 12] + profile[(root + 7) % 12]
            minor = profile[root] * 1.1 + profile[(root + 3) % 12] + profile[(root + 7) % 12]
            candidates.extend(((float(major), name), (float(minor), f"{name}m")))
        score, name = max(candidates, key=lambda item: item[0])
        return name, min(1.0, score / total)

    @classmethod
    def _estimate_key(cls, profile: np.ndarray) -> str:
        if float(np.sum(profile)) <= 1e-8:
            return "Unknown"
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.6, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        centered = profile - np.mean(profile)
        options: list[tuple[float, str]] = []
        for root, name in enumerate(cls._pitch_names):
            options.append((float(np.dot(centered, np.roll(major_profile, root))), f"{name} major"))
            options.append((float(np.dot(centered, np.roll(minor_profile, root))), f"{name} minor"))
        return max(options, key=lambda item: item[0])[1]

    @classmethod
    def _estimate_melody(cls, samples: np.ndarray, sample_rate: int, beats: list[float]) -> list[dict[str, Any]]:
        notes: list[dict[str, Any]] = []
        for index, beat in enumerate(beats[:180]):
            midi, strength = cls._dominant_note(samples, sample_rate, beat)
            if midi is None or strength < 1e-5:
                continue
            next_beat = beats[index + 1] if index + 1 < len(beats) else beat + 0.5
            if notes and notes[-1]["midi"] == midi and beat - float(notes[-1]["start"]) < 2.5:
                notes[-1]["duration"] = round(next_beat - float(notes[-1]["start"]), 3)
                continue
            notes.append({
                "start": round(beat, 3),
                "duration": round(max(0.12, (next_beat - beat) * 0.82), 3),
                "midi": midi,
                "name": cls._midi_name(midi),
                "confidence": round(min(1.0, strength * 4.0), 2),
            })
        return notes

    @staticmethod
    def _dominant_note(samples: np.ndarray, sample_rate: int, start_seconds: float) -> tuple[int | None, float]:
        size = 4096
        start = int(start_seconds * sample_rate)
        frame = samples[start : start + size]
        if len(frame) < size:
            frame = np.pad(frame, (0, size - len(frame)))
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(size)))
        frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate)
        mask = (frequencies >= 80.0) & (frequencies <= 1_200.0)
        if not np.any(mask):
            return None, 0.0
        selected_frequency = float(frequencies[mask][int(np.argmax(spectrum[mask]))])
        strength = float(np.max(spectrum[mask]) / max(1e-8, np.sum(spectrum)))
        midi = int(np.clip(round(69 + 12 * math.log2(selected_frequency / 440.0)), 36, 96))
        return midi, strength

    @staticmethod
    def _estimate_parts(samples: np.ndarray, sample_rate: int, envelope: np.ndarray) -> list[dict[str, str]]:
        size = min(16_384, len(samples))
        if size < 64:
            return []
        spectrum = np.abs(np.fft.rfft(samples[:size] * np.hanning(size)))
        frequencies = np.fft.rfftfreq(size, 1.0 / sample_rate)
        total = float(np.sum(spectrum)) or 1.0
        low = float(np.sum(spectrum[(frequencies >= 35) & (frequencies < 220)])) / total
        high = float(np.sum(spectrum[frequencies >= 2_000])) / total
        transient = float(np.mean(envelope > np.mean(envelope) + np.std(envelope)))
        parts = [{"name": "Harmony / chords", "confidence": "estimated", "detail": "พบพลังงานเสียงกลางที่ใช้สร้างคอร์ด"}]
        if low > 0.10:
            parts.append({"name": "Bass", "confidence": "likely", "detail": "พบพลังงานย่านต่ำเด่น"})
        if high > 0.12 or transient > 0.16:
            parts.append({"name": "Drums / percussion", "confidence": "likely", "detail": "พบทรานเชียนต์หรือย่านสูงเด่น"})
        parts.append({"name": "Melody / vocal", "confidence": "estimated", "detail": "สร้างจากแนวโน้ตเด่นในมิกซ์รวม"})
        return parts

    @classmethod
    def _write_outputs(cls, directory: Path, analysis: dict[str, Any]) -> None:
        tempo = float(analysis["tempo"]["bpm"])
        notes = analysis.get("notes", [])
        (directory / "arrangement.mid").write_bytes(cls._midi_bytes(notes, tempo))
        (directory / "chords.txt").write_text(cls._chord_text(analysis), encoding="utf-8")
        (directory / "guitar-tab.txt").write_text(cls._guitar_tab(analysis), encoding="utf-8")

    @classmethod
    def _chord_text(cls, analysis: dict[str, Any]) -> str:
        lines = [
            "MYCODEX MUSIC LAB · CHORD SHEET (ESTIMATED)",
            f"Key: {analysis['key']['name']}",
            f"Tempo: {analysis['tempo']['bpm']} BPM · Meter: {analysis['rhythm']['meter']} · Groove: {analysis['rhythm']['groove']}",
            "",
        ]
        for chord in analysis.get("chords", []):
            lines.append(f"[{cls._clock(float(chord['start']))}–{cls._clock(float(chord['end']))}] {chord['name']}  (confidence {chord['confidence']})")
        lines.extend(("", "Check every chord by ear before performance or publishing."))
        return "\n".join(lines) + "\n"

    @classmethod
    def _guitar_tab(cls, analysis: dict[str, Any]) -> str:
        if isinstance(analysis.get("tablature"), dict):
            return cls._source_tab_text(analysis)
        notes = analysis.get("notes", [])
        lines = [
            "MYCODEX MUSIC LAB · GUITAR TAB (MELODY OUTLINE · ESTIMATED)",
            f"Tempo: {analysis['tempo']['bpm']} BPM · Key: {analysis['key']['name']}",
            "Each slot follows the detected beat grid; verify by ear.",
            "",
        ]
        strings = [("e", 64), ("B", 59), ("G", 55), ("D", 50), ("A", 45), ("E", 40)]
        tab = {name: [] for name, _ in strings}
        for index, note in enumerate(notes[:96]):
            selected = cls._guitar_position(int(note["midi"]), strings)
            for name, _tuning in strings:
                tab[name].append(f"{selected[1]:02d}-" if selected and selected[0] == name else "---")
            if (index + 1) % 4 == 0:
                for name, _tuning in strings:
                    tab[name].append("|")
        if not notes:
            lines.append("No reliable melody outline was found. Use the chord sheet and listen manually.")
        else:
            lines.extend(f"{name}|{''.join(tab[name])}" for name, _ in strings)
        return "\n".join(lines) + "\n"

    @classmethod
    def _source_tab_text(cls, analysis: dict[str, Any]) -> str:
        tablature = analysis.get("tablature") or {}
        lines = [
            "MYCODEX MUSIC LAB · PDF TAB READOUT",
            f"Instrument: {tablature.get('instrument', 'Unknown')}",
            f"Tuning (top to bottom): {', '.join(tablature.get('tuning', []))}",
            f"Tempo: {analysis['tempo']['bpm']} BPM",
            "",
            "time     string  fret",
        ]
        for event in (tablature.get("events") or [])[:1_000]:
            value = "x (muted)" if event.get("muted") else str(event.get("fret", "?"))
            lines.append(f"{cls._clock(float(event.get('start', 0))):>5}     {event.get('string', '?'):>2}      {value}")
        lines.append("")
        lines.append("Read from positioned PDF TAB glyphs. Verify slides, ties and exact rhythm by eye.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _guitar_position(note: int, strings: list[tuple[str, int]]) -> tuple[str, int] | None:
        positions = [(name, note - tuning) for name, tuning in strings if 0 <= note - tuning <= 18]
        return min(positions, key=lambda item: item[1]) if positions else None

    @classmethod
    def _midi_bytes(cls, notes: list[dict[str, Any]], bpm: float, program: int = 0) -> bytes:
        ticks_per_beat = 480
        # "MyCodex MIDI" is 12 bytes.  A previous 11-byte metadata length made
        # some standards-compliant SoundFont players reject the exported MIDI.
        events: list[tuple[int, int, bytes]] = [(0, 0, b"\xff\x03\x0cMyCodex MIDI")]
        microseconds = int(60_000_000 / max(1.0, bpm))
        events.append((0, 0, b"\xff\x51\x03" + microseconds.to_bytes(3, "big", signed=False)))
        events.append((0, 0, bytes((0xC0, int(np.clip(program, 0, 127))))))
        for note in notes:
            tick = int(round(float(note["start"]) * bpm / 60.0 * ticks_per_beat))
            length = max(60, int(round(float(note["duration"]) * bpm / 60.0 * ticks_per_beat)))
            value = int(np.clip(int(note["midi"]), 0, 127))
            events.append((tick, 1, bytes((0x90, value, 92))))
            events.append((tick + length, 0, bytes((0x80, value, 0))))
        events.sort(key=lambda event: (event[0], event[1]))
        payload = bytearray()
        previous = 0
        for tick, _priority, message in events:
            payload.extend(cls._vlq(max(0, tick - previous)))
            payload.extend(message)
            previous = tick
        payload.extend(b"\x00\xff\x2f\x00")
        return b"MThd\x00\x00\x00\x06\x00\x00\x00\x01" + ticks_per_beat.to_bytes(2, "big") + b"MTrk" + len(payload).to_bytes(4, "big") + bytes(payload)

    @staticmethod
    def _vlq(value: int) -> bytes:
        encoded = [value & 0x7F]
        value >>= 7
        while value:
            encoded.append((value & 0x7F) | 0x80)
            value >>= 7
        return bytes(reversed(encoded))

    @classmethod
    def _artifact_urls(cls, music_id: str) -> dict[str, str]:
        return {name: f"/api/music/{music_id}/downloads/{name}" for name in cls._artifact_names}

    @classmethod
    def _track_response(cls, metadata: dict[str, Any], analyzed: bool = False) -> dict[str, object]:
        music_id = str(metadata.get("music_id", ""))
        kind = str(metadata.get("kind", "audio"))
        return {
            "music_id": music_id,
            "kind": kind,
            "file_name": str(metadata.get("file_name", "audio.wav")),
            "bytes": int(metadata.get("bytes", 0)),
            "duration_seconds": metadata.get("duration_seconds"),
            "analyzed": analyzed,
            "created_at": str(metadata.get("created_at", "")),
            "audio_url": f"/api/music/{music_id}/audio" if kind == "audio" else None,
            "source_url": f"/api/music/{music_id}/source",
        }

    @staticmethod
    def _midi_name(value: int) -> str:
        octaves = (value // 12) - 1
        return f"{MusicService._pitch_names[value % 12]}{octaves}"

    @staticmethod
    def _clock(seconds: float) -> str:
        minutes, remainder = divmod(max(0, int(seconds)), 60)
        return f"{minutes}:{remainder:02d}"

    @classmethod
    def _clean_filename(cls, value: str) -> str:
        candidate = Path(value or "audio.wav").name.strip()
        if not candidate or len(candidate) > 160:
            raise MusicError("ชื่อไฟล์เพลงไม่ถูกต้อง")
        return candidate

    @classmethod
    def _track_directory(cls, user_id: str, music_id: str) -> Path:
        if not cls._music_id_pattern.fullmatch(music_id):
            raise MusicError("ไม่พบไฟล์เพลงที่ร้องขอ")
        return cls._owner_directory(user_id) / music_id

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

    @classmethod
    def _owner_directory(cls, user_id: str) -> Path:
        owner_key = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:32]
        return Path(settings.agent_state_root).expanduser().resolve().parent / "music" / owner_key

    @classmethod
    def _trim_history(cls, user_id: str) -> None:
        directory = cls._owner_directory(user_id)
        try:
            entries = [item for item in directory.iterdir() if item.is_dir() and cls._music_id_pattern.fullmatch(item.name)]
            entries.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            stale = entries[cls._retention_per_user :]
            for item in stale:
                for child in item.iterdir():
                    child.unlink(missing_ok=True)
                item.rmdir()
        except OSError:
            return
