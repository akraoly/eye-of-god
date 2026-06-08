/**
 * Utilitaires voix — STT (expo-av v16 → backend) + TTS (expo-speech, voix homme).
 */
import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import { API_BASE, getToken, triggerLogout } from './api';

// ─── Nettoyage texte avant TTS ────────────────────────────────────────────────
function cleanForTTS(raw) {
  return raw
    .replace(/```[\s\S]*?```/g, ', exemple de code, ')
    .replace(/`[^`]+`/g, '')
    .replace(/#{1,6}\s*(.+)/g, '$1. ')
    .replace(/\*{1,3}([^*\n]+)\*{1,3}/g, '$1')
    .replace(/_{1,2}([^_\n]+)_{1,2}/g, '$1')
    .replace(/~~([^~\n]+)~~/g, '$1')
    .replace(/^[-*+]\s+(.+)/gm, '$1. ')
    .replace(/^\d+\.\s+(.+)/gm, '$1. ')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\|/g, ', ')
    .replace(/[-]{3,}/g, '')
    .replace(/[✅❌⚠️🔴🟠🟡🟢🔵⭕✓✗→←↑↓►◄•·🎯🔥💡⚡🛡️🔒🔓]/g, '')
    .replace(/[*#_~`^<>{}[\]\\]/g, '')
    .replace(/([.!?])\1+/g, '$1')
    .replace(/\.{2,}/g, '.')
    .replace(/,{2,}/g, ',')
    .replace(/\s*:\s*\n/g, ', ')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ', ')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[,\s]+\./g, '.')
    .replace(/\.\s*,/g, '.')
    .replace(/\.{2,}/g, '.')
    .replace(/\s+,/g, ',')
    .replace(/—/g, ', ')
    .trim()
    .slice(0, 3000);
}

// ─── TTS : parler un texte avec une voix d'homme ───────────────────────────

export async function speak(text, opts = {}) {
  if (!text?.trim()) return;

  Speech.stop();

  const options = {
    language: opts.language || 'fr-FR',
    pitch: opts.pitch ?? 0.01,
    rate: opts.rate ?? 1.20,
    volume: opts.volume ?? 1.0,
    onDone: opts.onDone,
    onError: opts.onError,
    ...opts,
  };

  try {
    const voices = await Speech.getAvailableVoicesAsync?.() || [];
    const male = voices.find(v =>
      v.language?.startsWith('fr') &&
      (v.name?.toLowerCase().includes('male') || v.name?.toLowerCase().includes('homme') || v.identifier?.toLowerCase().includes('male'))
    );
    if (male) options.voice = male.identifier;
  } catch (_) {}

  Speech.speak(cleanForTTS(text), options);
}

export function stopSpeaking() {
  Speech.stop();
}

export async function isSpeaking() {
  return Speech.isSpeakingAsync?.() ?? false;
}

// ─── STT : enregistrer et transcrire via le backend ────────────────────────

let _recording = null;

// Options d'enregistrement compatibles expo-av v16
const RECORDING_OPTIONS = {
  android: {
    extension: '.m4a',
    outputFormat: Audio.AndroidOutputFormat?.MPEG_4 ?? 2,
    audioEncoder: Audio.AndroidAudioEncoder?.AAC ?? 3,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
  },
  ios: {
    extension: '.m4a',
    outputFormat: Audio.IOSOutputFormat?.MPEG4AAC ?? 'aac ',
    audioQuality: Audio.IOSAudioQuality?.HIGH ?? 0x60,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 128000,
  },
  web: {},
};

export async function startRecording() {
  try {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== 'granted') throw new Error('Permission micro refusée');

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });

    // expo-av v16 : API createAsync recommandée
    const { recording: rec } = await Audio.Recording.createAsync(RECORDING_OPTIONS);
    _recording = rec;
    return rec;
  } catch (e) {
    _recording = null;
    throw new Error(`Enregistrement impossible : ${e.message}`);
  }
}

export async function stopRecordingAndTranscribe(language = 'fr-FR') {
  if (!_recording) throw new Error('Aucun enregistrement en cours');

  let uri = null;
  try {
    await _recording.stopAndUnloadAsync();
    uri = _recording.getURI();
    _recording = null;

    await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

    if (!uri) throw new Error('URI audio manquant après enregistrement');

    const token = await getToken();
    const formData = new FormData();
    formData.append('file', {
      uri,
      name: 'audio.m4a',
      type: 'audio/mp4',
    });
    formData.append('language', language);

    // Timeout 45s — Google STT peut être lent
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    let res;
    try {
      res = await fetch(`${API_BASE}/api/voice/transcribe`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // NE PAS mettre Content-Type : React Native le gère avec le boundary
        },
        body: formData,
        signal: controller.signal,
      });
    } catch (fetchErr) {
      if (fetchErr.name === 'AbortError') {
        throw new Error('Délai dépassé — serveur trop lent (>45s)');
      }
      // "Network request failed" → diagnostic précis
      throw new Error(`Serveur inaccessible (${API_BASE}) — vérifie que le backend tourne`);
    } finally {
      clearTimeout(timeoutId);
    }

    if (res.status === 401) {
      triggerLogout();
      throw new Error('Session expirée — reconnecte-toi');
    }

    if (!res.ok) {
      const err = await res.text().catch(() => `HTTP ${res.status}`);
      throw new Error(err || `HTTP ${res.status}`);
    }

    const data = await res.json();
    return {
      text: data.text || '',
      voice_energy: data.voice_energy || 'normal',
      voice_duration: data.voice_duration || 0,
    };
  } catch (e) {
    _recording = null;
    throw e;
  }
}

export function isRecording() {
  return !!_recording;
}
