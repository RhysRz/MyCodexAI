"""Optional high-quality Music Lab pipeline for disposable cloud runners.

The module deliberately imports no large ML package.  Demucs and Basic Pitch run
as isolated, trusted executables so the normal MyCodexAI process remains light and
the base DSP result can still be returned when an optional model is unavailable.
"""

from __future__ import annotations

import csv
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ElementTree

from app.core.settings import settings


class AdvancedMusicService:
    STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")
    TRANSCRIBED_STEMS = ("vocals", "bass", "guitar", "piano", "other")
    PROGRAMS = {"vocals": 53, "bass": 33, "guitar": 25, "piano": 0, "other": 48}
    LABELS = {
        "vocals": "เสียงร้อง", "drums": "กลอง", "bass": "เบส",
        "guitar": "กีตาร์", "piano": "เปียโน", "other": "เครื่องดนตรีอื่น",
    }

    @classmethod
    def available(cls) -> bool:
        return bool(settings.music_advanced_enabled and cls._executable(settings.music_ffmpeg_executable))

    @classmethod
    def enrich(cls, source: Path, analysis: dict[str, Any], directory: Path) -> dict[str, Any]:
        """Add stems and score artifacts without ever invalidating base analysis."""
        analysis["advanced_music"] = {
            "enabled": bool(settings.music_advanced_enabled),
            "status": "disabled",
            "model": settings.music_demucs_model,
            "fallback_used": True,
        }
        if not settings.music_advanced_enabled:
            return analysis
        for name in ("stems.mid", "advanced-score.musicxml", *(f"preview-{stem}.mp3" for stem in cls.STEMS)):
            try:
                (directory / name).unlink(missing_ok=True)
            except OSError:
                pass
        ffmpeg = cls._executable(settings.music_ffmpeg_executable)
        if not ffmpeg:
            cls._fallback(analysis, "ไม่พบ FFmpeg จึงใช้ผลวิเคราะห์พื้นฐาน")
            return analysis

        try:
            stems = cls._separate(source, directory)
            if not stems:
                cls._fallback(analysis, "โมเดลแยกเสียงไม่สร้าง stem จึงใช้ผลวิเคราะห์พื้นฐาน")
                return analysis
            notes_by_stem: dict[str, list[dict[str, Any]]] = {}
            transcription_errors: list[str] = []
            for stem in cls.TRANSCRIBED_STEMS:
                path = stems.get(stem)
                if not path:
                    continue
                try:
                    notes = cls._transcribe(path, directory / "transcription" / stem)
                except Exception as error:  # optional model failures are non-fatal
                    notes = []
                    transcription_errors.append(f"{cls.LABELS[stem]}: {str(error)[:120]}")
                if notes:
                    notes_by_stem[stem] = notes

            previews: dict[str, str] = {}
            for stem, path in stems.items():
                target = directory / f"preview-{stem}.mp3"
                cls._preview(ffmpeg, path, target)
                if target.is_file() and target.stat().st_size > 512:
                    previews[stem] = target.name

            bpm = float((analysis.get("tempo") or {}).get("bpm") or 120)
            if notes_by_stem:
                (directory / "stems.mid").write_bytes(cls._multitrack_midi(notes_by_stem, bpm))
                cls._write_musicxml(directory / "advanced-score.musicxml", notes_by_stem, bpm)

            detected = []
            for stem in cls.STEMS:
                if stem not in stems:
                    continue
                note_count = len(notes_by_stem.get(stem, []))
                detail = "แยกเป็น stem ด้วย Demucs"
                if stem != "drums":
                    detail += f" · ถอดได้ {note_count} โน้ต" if note_count else " · ยังถอดโน้ตไม่ได้อย่างมั่นใจ"
                detected.append({
                    "name": cls.LABELS[stem], "stem": stem, "confidence": "model",
                    "detail": detail, "note_count": note_count,
                })
            analysis["detected_parts"] = detected
            analysis["stem_separation"] = {
                "available": True,
                "model": settings.music_demucs_model,
                "stems": list(stems),
                "preview_seconds": settings.music_stem_preview_seconds,
                "detail": "แยกเสียงร้อง กลอง เบส กีตาร์ เปียโน และเสียงอื่นแล้ว พรีวิวเป็นไฟล์สั้นเพื่อไม่ให้ฐานข้อมูล Cloud เต็ม",
            }
            analysis["stem_transcription"] = {
                stem: {"label": cls.LABELS[stem], "note_count": len(notes), "notes": notes[:500]}
                for stem, notes in notes_by_stem.items()
            }
            analysis["advanced_music"] = {
                "enabled": True,
                "status": "completed",
                "model": settings.music_demucs_model,
                "fallback_used": False,
                "transcription_engine": "Basic Pitch" if cls._basic_pitch() else "unavailable",
                "transcription_warnings": transcription_errors,
                "exports": [name for name in ("MusicXML", "Multitrack MIDI") if notes_by_stem],
            }
            limitations = analysis.setdefault("limitations", [])
            if isinstance(limitations, list):
                limitations[:] = [item for item in limitations if "ยังไม่แยกเสียงร้อง" not in str(item)]
                limitations.append("การแยก stem และถอดโน้ตด้วย AI อาจมีเสียงรั่วหรือโน้ตคลาดเคลื่อน ควรตรวจใน DAW/โปรแกรมโน้ต")
            return analysis
        except Exception as error:
            cls._fallback(analysis, f"ขั้นสูงไม่สำเร็จ ({str(error)[:180]}) จึงคืนผลวิเคราะห์พื้นฐานแทน")
            return analysis
        finally:
            # Raw six-stem WAVs can be hundreds of MB.  Only short previews and
            # editable score artifacts survive the run.
            shutil.rmtree(directory / "separated", ignore_errors=True)
            shutil.rmtree(directory / "transcription", ignore_errors=True)

    @classmethod
    def _separate(cls, source: Path, directory: Path) -> dict[str, Path]:
        output = directory / "separated"
        command = [
            sys.executable, "-m", "demucs", "-n", settings.music_demucs_model,
            "-d", "cpu", "--shifts", "0", "--overlap", "0.1", "-j", "1",
            "--segment", "7.8", "-o", str(output), str(source),
        ]
        completed = subprocess.run(
            command, cwd=str(directory), capture_output=True, text=True,
            timeout=settings.music_demucs_timeout_seconds, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "Demucs failed")[-1_000:])
        found: dict[str, Path] = {}
        for stem in cls.STEMS:
            matches = list(output.rglob(f"{stem}.wav"))
            if matches:
                found[stem] = matches[0]
        return found

    @classmethod
    def _transcribe(cls, source: Path, output: Path) -> list[dict[str, Any]]:
        executable = cls._basic_pitch()
        if not executable:
            return []
        output.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [executable, str(output), str(source), "--save-note-events"],
            capture_output=True, text=True, timeout=settings.music_basic_pitch_timeout_seconds, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "Basic Pitch failed")[-800:])
        csv_files = sorted(output.glob("*.csv"))
        if not csv_files:
            return []
        return cls.parse_note_csv(csv_files[0])

    @staticmethod
    def parse_note_csv(source: Path) -> list[dict[str, Any]]:
        """Parse both current and older Basic Pitch note-event CSV headings."""
        notes: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {str(key or "").strip().casefold().replace(" ", "_"): value for key, value in row.items()}
                try:
                    start = float(normalized.get("start_time_s") or normalized.get("start_time") or normalized.get("onset") or 0)
                    end = float(normalized.get("end_time_s") or normalized.get("end_time") or normalized.get("offset") or start + 0.2)
                    pitch = int(round(float(normalized.get("pitch_midi") or normalized.get("midi_pitch") or normalized.get("pitch") or -1)))
                    confidence = float(normalized.get("amplitude") or normalized.get("confidence") or normalized.get("velocity") or 0.75)
                except (TypeError, ValueError):
                    continue
                if not 0 <= pitch <= 127 or end <= start:
                    continue
                notes.append({
                    "start": round(max(0.0, start), 4), "duration": round(min(30.0, end - start), 4),
                    "midi": pitch, "name": AdvancedMusicService._midi_name(pitch),
                    "confidence": round(max(0.0, min(1.0, confidence)), 3),
                })
        return sorted(notes, key=lambda item: (item["start"], item["midi"]))[:5_000]

    @classmethod
    def _preview(cls, ffmpeg: str, source: Path, target: Path) -> None:
        completed = subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-t", str(settings.music_stem_preview_seconds), "-ac", "2", "-ar", "44100",
            "-codec:a", "libmp3lame", "-b:a", "64k", str(target),
        ], capture_output=True, text=True, timeout=180, check=False)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or "FFmpeg preview failed")[-600:])

    @classmethod
    def _multitrack_midi(cls, tracks: dict[str, list[dict[str, Any]]], bpm: float) -> bytes:
        ticks_per_beat = 480
        microseconds = int(60_000_000 / max(1.0, bpm))
        tempo = b"\x00\xff\x51\x03" + microseconds.to_bytes(3, "big") + b"\x00\xff\x2f\x00"
        payloads = [b"MTrk" + len(tempo).to_bytes(4, "big") + tempo]
        for index, (stem, notes) in enumerate(tracks.items()):
            channel = index if index < 9 else index + 1
            name = cls.LABELS.get(stem, stem).encode("utf-8")[:100]
            events: list[tuple[int, int, bytes]] = [
                (0, 0, b"\xff\x03" + bytes((len(name),)) + name),
                (0, 0, bytes((0xC0 | channel, cls.PROGRAMS.get(stem, 0)))),
            ]
            for note in notes:
                start = int(round(float(note["start"]) * bpm / 60 * ticks_per_beat))
                length = max(30, int(round(float(note["duration"]) * bpm / 60 * ticks_per_beat)))
                pitch = max(0, min(127, int(note["midi"])))
                velocity = max(35, min(118, int(float(note.get("confidence", 0.75)) * 110)))
                events.extend(((start, 1, bytes((0x90 | channel, pitch, velocity))), (start + length, 0, bytes((0x80 | channel, pitch, 0)))))
            events.sort(key=lambda item: (item[0], item[1]))
            body, previous = bytearray(), 0
            for tick, _priority, message in events:
                body.extend(cls._vlq(max(0, tick - previous)))
                body.extend(message)
                previous = tick
            body.extend(b"\x00\xff\x2f\x00")
            payloads.append(b"MTrk" + len(body).to_bytes(4, "big") + bytes(body))
        header = b"MThd\x00\x00\x00\x06\x00\x01" + len(payloads).to_bytes(2, "big") + ticks_per_beat.to_bytes(2, "big")
        return header + b"".join(payloads)

    @classmethod
    def _write_musicxml(cls, target: Path, tracks: dict[str, list[dict[str, Any]]], bpm: float) -> None:
        root = ElementTree.Element("score-partwise", version="4.0")
        work = ElementTree.SubElement(root, "work")
        ElementTree.SubElement(work, "work-title").text = "MyCodex Advanced Transcription"
        part_list = ElementTree.SubElement(root, "part-list")
        for index, stem in enumerate(tracks, 1):
            score_part = ElementTree.SubElement(part_list, "score-part", id=f"P{index}")
            ElementTree.SubElement(score_part, "part-name").text = cls.LABELS.get(stem, stem)
        divisions = 480
        for index, (stem, notes) in enumerate(tracks.items(), 1):
            part = ElementTree.SubElement(root, "part", id=f"P{index}")
            measure = ElementTree.SubElement(part, "measure", number="1")
            attributes = ElementTree.SubElement(measure, "attributes")
            ElementTree.SubElement(attributes, "divisions").text = str(divisions)
            time = ElementTree.SubElement(attributes, "time")
            ElementTree.SubElement(time, "beats").text = "4"
            ElementTree.SubElement(time, "beat-type").text = "4"
            direction = ElementTree.SubElement(measure, "direction", placement="above")
            ElementTree.SubElement(direction, "sound", tempo=str(round(bpm, 2)))
            current = 0
            for item in notes[:2_000]:
                start = max(current, int(round(float(item["start"]) * bpm / 60 * divisions)))
                gap = start - current
                if gap:
                    forward = ElementTree.SubElement(measure, "forward")
                    ElementTree.SubElement(forward, "duration").text = str(gap)
                length = max(30, int(round(float(item["duration"]) * bpm / 60 * divisions)))
                note = ElementTree.SubElement(measure, "note")
                pitch = ElementTree.SubElement(note, "pitch")
                step, alter, octave = cls._musicxml_pitch(int(item["midi"]))
                ElementTree.SubElement(pitch, "step").text = step
                if alter:
                    ElementTree.SubElement(pitch, "alter").text = str(alter)
                ElementTree.SubElement(pitch, "octave").text = str(octave)
                ElementTree.SubElement(note, "duration").text = str(length)
                ElementTree.SubElement(note, "voice").text = "1"
                current = start + length
        ElementTree.indent(root, space="  ")
        ElementTree.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _musicxml_pitch(midi: int) -> tuple[str, int, int]:
        names = (("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0), ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0))
        step, alter = names[midi % 12]
        return step, alter, midi // 12 - 1

    @staticmethod
    def _midi_name(value: int) -> str:
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        return f"{names[value % 12]}{value // 12 - 1}"

    @staticmethod
    def _vlq(value: int) -> bytes:
        encoded = [value & 0x7F]
        value >>= 7
        while value:
            encoded.append((value & 0x7F) | 0x80)
            value >>= 7
        return bytes(reversed(encoded))

    @staticmethod
    def _executable(value: str) -> str | None:
        if not value:
            return None
        path = Path(value)
        if path.is_file():
            return str(path.resolve())
        return shutil.which(value)

    @classmethod
    def _basic_pitch(cls) -> str | None:
        return cls._executable(settings.music_basic_pitch_executable)

    @staticmethod
    def _fallback(analysis: dict[str, Any], detail: str) -> None:
        analysis["advanced_music"] = {
            "enabled": True, "status": "fallback", "model": settings.music_demucs_model,
            "fallback_used": True, "detail": detail,
        }
        limitations = analysis.setdefault("limitations", [])
        if isinstance(limitations, list):
            limitations.append(detail)
