/**
 * Utilitaires voix — STT (expo-av → backend) + TTS (expo-speech, voix homme).
 */
import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import { API_BASE, getToken } from './api';

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

  // Arrêter toute lecture en cours
  Speech.stop();

  const options = {
    language: opts.language || 'fr-FR',
    pitch: opts.pitch ?? 0.60,   // très grave — voix homme
    rate: opts.rate ?? 1.08,     // rapide et fluide
    volume: opts.volume ?? 1.0,
    onDone: opts.onDone,
    onError: opts.onError,
    ...opts,
  };

  // Sur Android, cherche une voix masculine si disponible
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

export async function startRecording() {
  try {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== 'granted') throw new Error('Permission micro refusée');

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });

    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync({
      android: {
        extension: '.m4a',
        outputFormat: Audio.AndroidOutputFormat.MPEG_4,
        audioEncoder: Audio.AndroidAudioEncoder.AAC,
        sampleRate: 16000,
        numberOfChannels: 1,
        bitRate: 128000,
      },
      ios: {
        extension: '.m4a',
        outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
        audioQuality: Audio.IOSAudioQuality.HIGH,
        sampleRate: 16000,
        numberOfChannels: 1,
        bitRate: 128000,
      },
      web: {},
    });

    await rec.startAsync();
    _recording = rec;
    return rec;
  } catch (e) {
    throw new Error(`Enregistrement impossible : ${e.message}`);
  }
}

export async function stopRecordingAndTranscribe(language = 'fr-FR') {
  if (!_recording) throw new Error('Aucun enregistrement en cours');

  try {
    await _recording.stopAndUnloadAsync();
    const uri = _recording.getURI();
    _recording = null;

    await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

    if (!uri) throw new Error('URI audio manquant');

    // Envoyer au backend pour transcription
    const token = await getToken();
    const formData = new FormData();
    formData.append('file', {
      uri,
      name: 'audio.m4a',
      type: 'audio/mp4',
    });
    formData.append('language', language);

    const res = await fetch(`${API_BASE}/api/voice/transcribe`, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `HTTP ${res.status}`);
    }

    const data = await res.json();
    // Retourner le texte + les métadonnées vocales pour la détection d'émotion
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
