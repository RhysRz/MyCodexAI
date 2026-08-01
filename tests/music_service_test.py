"""Music Lab exports stay owner-scoped and produce editable local artifacts."""

from array import array
from math import pi, sin
from pathlib import Path
from tempfile import TemporaryDirectory
import wave

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services.music_service import MusicError, MusicService


def wav_bytes() -> bytes:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "test.wav"
        rate, seconds = 8_000, 8
        samples = array("h")
        for index in range(rate * seconds):
            time = index / rate
            pulse = 1.0 if (time % 0.5) < 0.045 else 0.24
            value = pulse * (0.52 * sin(2 * pi * 261.63 * time) + 0.33 * sin(2 * pi * 329.63 * time) + 0.28 * sin(2 * pi * 392.0 * time))
            samples.append(max(-32767, min(32767, int(value * 10_000))))
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(samples.tobytes())
        return path.read_bytes()


def chord_pdf_bytes() -> bytes:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "chords.pdf"
        document = canvas.Canvas(str(path))
        document.drawString(72, 720, "Song chart - Tempo: 96 BPM - 4/4")
        document.drawString(72, 690, "| C | Am | F | G | C | Am | F | G |")
        document.save()
        return path.read_bytes()


class _VectorTabPage:
    """Tiny positioned-text stand-in for a six-string guitar TAB PDF page."""

    def extract_text(self, visitor_text=None):
        if visitor_text:
            for row, fret in enumerate(("3", "0", "0", "0", "2", "3")):
                visitor_text(fret, None, (1, 0, 0, 1, 260 + row * 8, 300 + row * 48), None, 56)
        return ""


class _VectorTabReader:
    pages = [_VectorTabPage()]


class _RasterTabImage:
    def __init__(self, image):
        self.image = image


class _RasterTabPage:
    def __init__(self, image):
        self.images = [_RasterTabImage(image)]


class _RasterTabReader:
    def __init__(self, image):
        self.pages = [_RasterTabPage(image)]


def test_music_lab_creates_private_midi_chord_and_tab_exports():
    original_root = settings.agent_state_root
    owner = AuthenticatedUser("music-owner", "owner", "user")
    other = AuthenticatedUser("music-other", "other", "user")
    try:
        with TemporaryDirectory() as directory:
            settings.agent_state_root = str(Path(directory) / "runs")
            track = MusicService.create(owner, "practice.wav", wav_bytes())
            assert track["music_id"]
            assert MusicService.list_for(owner)[0]["file_name"] == "practice.wav"

            analysis = MusicService.analyze(owner, str(track["music_id"]))
            assert 60 <= analysis["tempo"]["bpm"] <= 200
            assert analysis["chords"]
            assert "midi" in analysis["artifacts"]
            midi, _type, _name = MusicService.artifact_for(owner, str(track["music_id"]), "midi")
            assert midi.read_bytes().startswith(b"MThd")
            tab, _type, _name = MusicService.artifact_for(owner, str(track["music_id"]), "tab")
            assert "GUITAR TAB" in tab.read_text(encoding="utf-8")
            try:
                MusicService.audio_path_for(other, str(track["music_id"]))
            except MusicError:
                pass
            else:
                raise AssertionError("another user must not access private music")

            sheet = MusicService.create(owner, "chords.pdf", chord_pdf_bytes())
            assert sheet["kind"] == "sheet"
            assert sheet["audio_url"] is None
            sheet_analysis = MusicService.analyze(owner, str(sheet["music_id"]))
            assert sheet_analysis["tempo"]["bpm"] == 96
            assert [item["name"] for item in sheet_analysis["chords"][:4]] == ["C", "Am", "F", "G"]
            source, media_type, _name = MusicService.source_path_for(owner, str(sheet["music_id"]))
            assert media_type == "application/pdf" and source.read_bytes().startswith(b"%PDF")
    finally:
        settings.agent_state_root = original_root


def test_vector_tab_reader_keeps_the_source_string_and_fret():
    tablature = MusicService._extract_vector_tablature(_VectorTabReader(), 120)
    assert tablature["instrument"] == "6-string guitar"
    assert tablature["string_count"] == 6
    assert tablature["tuning"] == ["e4", "B3", "G3", "D3", "A2", "E2"]
    assert tablature["notes"][0]["string"] == "e"
    assert tablature["notes"][0]["fret"] == 3
    assert tablature["notes"][0]["midi"] == 67
    analysis = MusicService._analysis_from_tablature(tablature, 120, 1, True)
    assert "string  fret" in MusicService._guitar_tab(analysis)


def test_raster_tab_reader_detects_six_strings_and_keeps_frets(monkeypatch):
    image = Image.new("L", (900, 420), 255)
    drawing = ImageDraw.Draw(image)
    rows = [120 + index * 24 for index in range(6)]
    for row in rows:
        drawing.line((80, row, 820, row), fill=0, width=2)
    monkeypatch.setattr(settings, "music_tab_ocr_executable", "trusted-tesseract")
    monkeypatch.setattr(MusicService, "_tab_ocr_executable", staticmethod(lambda: "trusted-tesseract"))
    monkeypatch.setattr(
        MusicService,
        "_ocr_raster_tab_glyphs",
        staticmethod(lambda _gray, groups, _executable, _path: [
            {"token": token, "x": 180 + index * 60, "y": groups[0][index]}
            for index, token in enumerate(("3", "0", "0", "0", "2", "3"))
        ]),
    )
    tablature = MusicService._extract_raster_tablature(_RasterTabReader(image), 120)
    assert tablature["instrument"] == "6-string guitar"
    assert tablature["string_count"] == 6
    assert [(note["string"], note["fret"]) for note in tablature["notes"]] == [
        ("e", 3), ("B", 0), ("G", 0), ("D", 0), ("A", 2), ("E", 3),
    ]


def test_musicxml_omr_output_becomes_editable_notes():
    xml = """<?xml version='1.0' encoding='UTF-8'?>
    <score-partwise version='3.1'><part-list><score-part id='P1'><part-name>Piano</part-name></score-part></part-list>
    <part id='P1'><measure number='1'><attributes><divisions>2</divisions><time><beats>3</beats><beat-type>4</beat-type></time></attributes>
    <direction><sound tempo='90'/></direction>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration></note>
    <note><pitch><step>E</step><alter>-1</alter><octave>4</octave></pitch><duration>2</duration></note>
    </measure></part></score-partwise>"""
    with TemporaryDirectory() as directory:
        score = Path(directory) / "score.musicxml"
        score.write_text(xml, encoding="utf-8")
        analysis = MusicService._analysis_from_musicxml(score, 1)
    assert analysis["tempo"]["bpm"] == 90
    assert analysis["rhythm"]["meter"] == "3/4 (from OMR)"
    assert [note["name"] for note in analysis["notes"]] == ["C4", "D#4"]


def test_midi_export_has_a_valid_track_name_length_and_program_change():
    data = MusicService._midi_bytes([{"start": 0, "duration": 0.5, "midi": 60}], 120, program=25)
    assert b"\xff\x03\x0cMyCodex MIDI" in data
    assert b"\xc0\x19" in data


def test_sample_renderer_has_a_memory_guard_and_high_quality_sample_rate():
    source = Path("app/services/music_service.py").read_text(encoding="utf-8")
    assert "music_render_min_available_mb" in source
    assert '"-r", "48000"' in source
    assert "ResourceService.snapshot()" in source
