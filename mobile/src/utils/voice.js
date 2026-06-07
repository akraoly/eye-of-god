/**
 * Utilitaires voix — STT (expo-av → backend) + TTS (expo-speech, voix homme).
 */
import * as Speech from 'expo-speech';
import { Audio } from 'expo-av';
import { API_BASE, getToken } from './api';

// ─── TTS : parler un texte avec une voix d'homme ───────────────────────────

export async function speak(text, opts = {}) {
  if (!text?.trim()) return;

  // Arrêter toute lecture en cours
  Speech.stop();

  const options = {
    language: opts.language || 'fr-FR',
    pitch: opts.pitch ?? 0.85,          // < 1 = voix plus grave (homme)
    rate: opts.rate ?? 0.92,            // légèrement plus lent pour clarté
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

  Speech.speak(text, options);
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
    return data.text || '';
  } catch (e) {
    _recording = null;
    throw e;
  }
}

export function isRecording() {
  return !!_recording;
}
