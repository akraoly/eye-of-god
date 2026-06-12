/**
 * Utilitaires voix — STT (expo-av v16 → backend) + TTS (expo-speech, voix homme).
 */
import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import { getApiBase, getToken, triggerLogout } from './api';

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

// ─── TTS : parler un texte avec une voix d'homme ──────────────────────────────
export async function speak(text, opts = {}) {
  if (!text?.trim()) return;
  Speech.stop();
  const options = {
    language: opts.language || 'fr-FR',
    pitch: opts.pitch ?? 1.0,
    rate: opts.rate ?? 1.0,
    volume: opts.volume ?? 1.0,
    onDone: opts.onDone,
    onError: opts.onError,
    ...opts,
  };
  try {
    const voices = await Speech.getAvailableVoicesAsync?.() || [];
    const fr = voices.find(v => v.language?.startsWith('fr'));
    if (fr) options.voice = fr.identifier;
  } catch (_) {}
  Speech.speak(cleanForTTS(text), options);
}

export function stopSpeaking() { Speech.stop(); }

export async function isSpeaking() {
  return Speech.isSpeakingAsync?.() ?? false;
}

// ─── STT : enregistrer et transcrire via le backend ───────────────────────────
let _recording = null;

const STT_RECORDING_OPTIONS = {
  android: {
    extension: '.m4a',
    outputFormat: 2,   // MPEG_4
    audioEncoder: 3,   // AAC
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 32000,
  },
  ios: {
    extension: '.m4a',
    audioQuality: 0x60, // HIGH
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 32000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {},
};

const AUDIO_MODE_RECORDING = {
  allowsRecordingIOS: true,
  playsInSilentModeIOS: true,
  staysActiveInBackground: false,
};

const AUDIO_MODE_PLAYBACK = {
  allowsRecordingIOS: false,
  playsInSilentModeIOS: true,  // garder true pour que le TTS fonctionne en mode silencieux iOS
  staysActiveInBackground: false,
};

export async function startRecording() {
  // Nettoyer tout enregistrement précédent bloqué
  if (_recording) {
    try { await _recording.stopAndUnloadAsync(); } catch (_) {}
    _recording = null;
  }

  try {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== 'granted') throw new Error('Autorise l\'accès au microphone dans les Réglages');

    // Configurer la session audio iOS AVANT de créer l'enregistreur
    await Audio.setAudioModeAsync(AUDIO_MODE_RECORDING);

    // Délai requis : iOS a besoin de 150ms pour activer la session audio
    await new Promise(r => setTimeout(r, 150));

    const { recording: rec } = await Audio.Recording.createAsync(STT_RECORDING_OPTIONS);
    _recording = rec;
    return rec;
  } catch (e) {
    _recording = null;
    await Audio.setAudioModeAsync(AUDIO_MODE_PLAYBACK).catch(() => {});
    throw new Error(`Micro inaccessible : ${e.message}`);
  }
}

export async function stopRecordingAndTranscribe(language = 'fr-FR') {
  if (!_recording) throw new Error('Aucun enregistrement en cours');

  let uri = null;
  try {
    await _recording.stopAndUnloadAsync();
    uri = _recording.getURI();
    _recording = null;

    // Restaurer le mode lecture (playsInSilentModeIOS: true pour que le TTS marche après)
    await Audio.setAudioModeAsync(AUDIO_MODE_PLAYBACK);

    if (!uri) throw new Error('URI audio manquant après enregistrement');

    const base = await getApiBase();
    const token = await getToken();
    const formData = new FormData();
    formData.append('file', {
      uri,
      name: 'audio.m4a',
      type: 'audio/mp4',
    });
    formData.append('language', language);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    let res;
    try {
      res = await fetch(`${base}/api/voice/transcribe`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // NE PAS mettre Content-Type : React Native gère le boundary multipart
        },
        body: formData,
        signal: controller.signal,
      });
    } catch (fetchErr) {
      if (fetchErr.name === 'AbortError') {
        throw new Error('Délai dépassé — serveur trop lent (>45s)');
      }
      throw new Error(`Serveur inaccessible (${base}) — vérifie que le backend tourne`);
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
