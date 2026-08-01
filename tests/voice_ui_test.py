from pathlib import Path


def test_voice_controls_are_available_for_chat_and_remote_without_server_side_audio_capture():
    voice = Path("static/voice.js").read_text(encoding="utf-8")
    page = Path("templates/index.html").read_text(encoding="utf-8")
    script = Path("static/script.js").read_text(encoding="utf-8")
    remote_page = Path("templates/remote.html").read_text(encoding="utf-8")
    remote_script = Path("static/remote.js").read_text(encoding="utf-8")

    assert "SpeechRecognition || window.webkitSpeechRecognition" in voice
    assert "speechSynthesis" in voice
    assert "preferredVoice" in voice
    assert 'id="voice-input"' in page
    assert 'id="voice-conversation"' in page
    assert 'id="voice-command"' in page
    assert 'id="voice-auto-read"' in page
    assert "listenForTask" in script
    assert "listenForVoiceConversation" in script
    assert "stopVoiceConversation" in script
    assert "listenForComputerCommand" in script
    assert "announceVoiceCommandUpdate" in script
    assert "voiceCommandRunId" in script
    assert "streamChatAnswer" in script
    assert "queueVoiceStreamDelta" in script
    assert "resumeVoice" in script
    assert "fetch('/api/chat/stream'" in script
    assert 'id="remote-voice-input"' in remote_page
    assert 'id="remote-voice-command"' in remote_page
    assert 'id="remote-answer-speak"' in remote_page
    assert "listenForRemoteTask" in remote_script
    assert "listenForRemoteCommand" in remote_script
    assert "speakRemoteAnswer" in remote_script
    assert "remoteElements.task.value" in remote_script
