(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let activeRecognition = null;

    function inputErrorMessage(code) {
        return {
            'not-allowed': 'เบราว์เซอร์ไม่ได้รับอนุญาตให้ใช้ไมโครโฟน',
            'service-not-allowed': 'บริการแปลงเสียงของเบราว์เซอร์ถูกปิดอยู่',
            'audio-capture': 'ไม่พบไมโครโฟนที่ใช้งานได้',
            'network': 'บริการแปลงเสียงต้องเชื่อมต่ออินเทอร์เน็ต',
            'no-speech': 'ไม่ได้ยินเสียงพูด ลองกดไมโครโฟนแล้วพูดใหม่',
        }[code] || 'ไม่สามารถแปลงเสียงเป็นข้อความได้';
    }

    function isListening() {
        return Boolean(activeRecognition);
    }

    function stopListening() {
        if (!activeRecognition) return;
        const recognition = activeRecognition;
        activeRecognition = null;
        try { recognition.stop(); } catch { /* Browser already stopped it. */ }
    }

    function listen({ lang = 'th-TH', onStart, onTranscript, onEnd, onError } = {}) {
        if (!Recognition) {
            onError?.('เบราว์เซอร์นี้ยังไม่รองรับการฟังเสียงในหน้าเว็บ ใช้ไมโครโฟนบนคีย์บอร์ดเพื่อพิมพ์เสียงแทนได้');
            return false;
        }

        stopListening();
        const recognition = new Recognition();
        recognition.lang = lang;
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => onStart?.();
        recognition.onresult = (event) => {
            let transcript = '';
            let final = true;
            for (let index = 0; index < event.results.length; index += 1) {
                transcript += event.results[index][0].transcript;
                final = final && event.results[index].isFinal;
            }
            onTranscript?.(transcript.trim(), final);
        };
        recognition.onerror = (event) => {
            if (event.error !== 'aborted') onError?.(inputErrorMessage(event.error));
        };
        recognition.onend = () => {
            if (activeRecognition === recognition) activeRecognition = null;
            onEnd?.();
        };

        activeRecognition = recognition;
        try {
            recognition.start();
            return true;
        } catch {
            activeRecognition = null;
            onError?.('ไม่สามารถเริ่มใช้ไมโครโฟนได้ ลองอนุญาตสิทธิ์ไมโครโฟนแล้วเริ่มใหม่');
            return false;
        }
    }

    function preferredVoice(lang) {
        const normalizedLanguage = String(lang || '').toLowerCase().split('-')[0];
        const voices = window.speechSynthesis.getVoices();
        const matchingVoices = voices.filter((voice) => voice.lang.toLowerCase().startsWith(normalizedLanguage));
        // Windows and mobile browsers use different voice catalogues.  Prefer a
        // Thai male voice when it exists, otherwise use the platform default
        // Thai voice rather than an English voice attempting to pronounce Thai.
        return matchingVoices.find((voice) => /pattara|male|ชาย/i.test(voice.name)) || matchingVoices[0] || null;
    }

    function speak(text, { lang = 'th-TH', onStart, onEnd, onError } = {}) {
        if (!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance) {
            onError?.('เบราว์เซอร์นี้ยังไม่รองรับการอ่านออกเสียง');
            return false;
        }
        const content = String(text || '').trim();
        if (!content) return false;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(content.slice(0, 12000));
        utterance.lang = lang;
        utterance.voice = preferredVoice(lang);
        utterance.rate = 0.96;
        utterance.pitch = 0.92;
        utterance.onstart = () => onStart?.();
        utterance.onend = () => onEnd?.();
        utterance.onerror = () => onError?.('ไม่สามารถอ่านออกเสียงได้');
        window.speechSynthesis.speak(utterance);
        return true;
    }

    window.MyCodexVoice = {
        inputSupported: Boolean(Recognition),
        outputSupported: 'speechSynthesis' in window && Boolean(window.SpeechSynthesisUtterance),
        isListening,
        listen,
        stopListening,
        speak,
        stopSpeaking: () => window.speechSynthesis?.cancel(),
    };
})();
