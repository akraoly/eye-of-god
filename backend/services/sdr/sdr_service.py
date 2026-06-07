"""
SDRService — Software Defined Radio operations.
Supports HackRF, RTL-SDR, BladeRF. Falls back to simulation if no hardware.
"""
from __future__ import annotations

import asyncio
import csv
import io
import math
import os
import random
import shutil
import struct
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

# Ensure recordings directory exists at module load
_RECORDINGS_DIR = Path("./data/sdr_recordings")
_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Known FM broadcast frequencies (MHz) for simulation
_FM_PEAKS = [88.0, 92.1, 95.3, 98.7, 103.4, 107.9]
_KNOWN_FREQS = _FM_PEAKS + [162.400, 1090.0]  # AIS, ADS-B


class SDRService:
    """Software Defined Radio service with hardware detection and simulation fallback."""

    # ── Hardware Detection ────────────────────────────────────────────────────

    async def detect_hardware(self) -> dict[str, Any]:
        """
        Probe available SDR hardware via CLI tool presence and quick invocation.
        Returns availability dict with simulation_mode flag.
        """
        hackrf = bool(shutil.which("hackrf_info"))
        rtlsdr = bool(shutil.which("rtl_test"))
        bladerf = bool(shutil.which("bladeRF-cli"))

        available: list[str] = []
        if hackrf:
            available.append("hackrf")
        if rtlsdr:
            available.append("rtlsdr")
        if bladerf:
            available.append("bladerf")

        # Quick sanity probe for RTL-SDR (non-blocking, 1-second timeout)
        rtlsdr_confirmed = False
        if rtlsdr:
            try:
                proc = await asyncio.create_subprocess_exec(
                    shutil.which("rtl_test"), "-t",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=2.0)
                    rtlsdr_confirmed = b"Found" in (stderr or b"")
                except asyncio.TimeoutError:
                    proc.kill()
                    rtlsdr_confirmed = True  # Tool exists; timeout means device busy
            except Exception:
                pass

        simulation_mode = len(available) == 0

        return {
            "hackrf": hackrf,
            "rtlsdr": rtlsdr,
            "bladerf": bladerf,
            "rtlsdr_confirmed": rtlsdr_confirmed,
            "available": available,
            "simulation_mode": simulation_mode,
        }

    # ── Frequency Scan ────────────────────────────────────────────────────────

    async def scan_frequencies(
        self,
        start_mhz: float = 88.0,
        end_mhz: float = 108.0,
        step_hz: int = 10000,
        gain: int = 40,
    ) -> dict[str, Any]:
        """
        Scan a frequency range and return power measurements.
        Uses rtl_power / hackrf_sweep if available, otherwise simulation.
        """
        hw = await self.detect_hardware()

        if hw["rtlsdr"] and shutil.which("rtl_power"):
            return await self._rtl_power_scan(start_mhz, end_mhz, step_hz, gain)
        if hw["hackrf"] and shutil.which("hackrf_sweep"):
            return await self._hackrf_sweep_scan(start_mhz, end_mhz, gain)

        return self._simulation_scan(start_mhz, end_mhz)

    async def _rtl_power_scan(
        self, start_mhz: float, end_mhz: float, step_hz: int, gain: int
    ) -> dict[str, Any]:
        rtl_power = shutil.which("rtl_power")
        outfile = _RECORDINGS_DIR / f"scan_{uuid.uuid4().hex[:8]}.csv"
        cmd = [
            rtl_power,
            "-f", f"{start_mhz}M:{end_mhz}M:{step_hz}",
            "-g", str(gain),
            "-1",
            str(outfile),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            return self._simulation_scan(start_mhz, end_mhz)
        except Exception:
            return self._simulation_scan(start_mhz, end_mhz)

        # Parse CSV output from rtl_power
        signals: list[dict] = []
        if outfile.exists():
            try:
                content = outfile.read_text()
                reader = csv.reader(io.StringIO(content))
                for row in reader:
                    if len(row) < 7:
                        continue
                    try:
                        freq_low = float(row[2])
                        freq_step = float(row[4])
                        values = [float(v) for v in row[6:] if v.strip()]
                        for i, val in enumerate(values):
                            signals.append({
                                "frequency_mhz": round((freq_low + i * freq_step) / 1e6, 3),
                                "power_dbm": round(val, 1),
                            })
                    except (ValueError, IndexError):
                        continue
                outfile.unlink(missing_ok=True)
            except Exception:
                return self._simulation_scan(start_mhz, end_mhz)

        if not signals:
            return self._simulation_scan(start_mhz, end_mhz)

        peaks = sorted(signals, key=lambda x: x["power_dbm"], reverse=True)[:5]
        return {
            "start_mhz": start_mhz,
            "end_mhz": end_mhz,
            "signals": signals,
            "peaks": peaks,
            "simulated": False,
            "hardware": "rtlsdr",
        }

    async def _hackrf_sweep_scan(
        self, start_mhz: float, end_mhz: float, gain: int
    ) -> dict[str, Any]:
        hackrf_sweep = shutil.which("hackrf_sweep")
        cmd = [
            hackrf_sweep,
            "-f", f"{int(start_mhz)}:{int(end_mhz)}",
            "-l", str(gain),
            "-g", str(gain),
            "-w", "500000",
        ]
        signals: list[dict] = []
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            except asyncio.TimeoutError:
                proc.kill()
                return self._simulation_scan(start_mhz, end_mhz)

            for line in (stdout or b"").decode(errors="ignore").splitlines():
                parts = line.split(",")
                if len(parts) >= 7:
                    try:
                        freq_low = float(parts[2])
                        freq_high = float(parts[3])
                        step = float(parts[4])
                        vals = [float(v) for v in parts[6:] if v.strip()]
                        n = len(vals)
                        for i, val in enumerate(vals):
                            f = freq_low + (freq_high - freq_low) * i / max(n - 1, 1)
                            signals.append({
                                "frequency_mhz": round(f / 1e6, 3),
                                "power_dbm": round(val, 1),
                            })
                    except (ValueError, IndexError):
                        continue
        except Exception:
            return self._simulation_scan(start_mhz, end_mhz)

        if not signals:
            return self._simulation_scan(start_mhz, end_mhz)

        peaks = sorted(signals, key=lambda x: x["power_dbm"], reverse=True)[:5]
        return {
            "start_mhz": start_mhz,
            "end_mhz": end_mhz,
            "signals": signals,
            "peaks": peaks,
            "simulated": False,
            "hardware": "hackrf",
        }

    # ── Listen ────────────────────────────────────────────────────────────────

    async def listen_frequency(
        self,
        frequency_mhz: float,
        sample_rate: int = 2_000_000,
        gain: int = 40,
        duration: int = 10,
        modulation: str = "fm",
    ) -> dict[str, Any]:
        """
        Tune to a frequency and demodulate audio. Returns path to WAV file.
        """
        hw = await self.detect_hardware()
        rec_id = uuid.uuid4().hex[:8]
        output_wav = str(_RECORDINGS_DIR / f"listen_{rec_id}.wav")

        if hw["rtlsdr"] and shutil.which("rtl_fm") and shutil.which("sox"):
            rtl_fm = shutil.which("rtl_fm")
            sox = shutil.which("sox")
            mod_flag = modulation.lower()
            cmd = (
                f"{rtl_fm} -f {frequency_mhz}M -M {mod_flag} "
                f"-s 200000 -r 48000 -g {gain} - | "
                f"{sox} -r 48000 -t raw -e s -b 16 - {output_wav} trim 0 {duration}"
            )
            # NOTE: Using shell=True is intentional here for pipe chaining; however
            # we avoid it below when possible. The binary guards are already done.
            try:
                proc = await asyncio.create_subprocess_exec(
                    "/bin/sh", "-c", cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
                simulated = False
                hardware = "rtlsdr"
            except Exception:
                self._write_silent_wav(output_wav, duration)
                simulated = True
                hardware = "simulation"
        else:
            self._write_silent_wav(output_wav, duration)
            simulated = True
            hardware = "simulation"

        file_size = os.path.getsize(output_wav) if os.path.exists(output_wav) else 0
        return {
            "recording_id": rec_id,
            "frequency_mhz": frequency_mhz,
            "modulation": modulation,
            "duration": duration,
            "file_path": output_wav,
            "file_size": file_size,
            "simulated": simulated,
            "hardware": hardware,
        }

    # ── Demodulate ────────────────────────────────────────────────────────────

    async def demodulate_signal(
        self,
        input_file: str,
        modulation: str = "fm",
        output_format: str = "wav",
    ) -> dict[str, Any]:
        """
        Convert a raw IQ file or WAV to demodulated audio using sox.
        """
        output_file = input_file.replace(".iq", f"_demod.{output_format}")
        sox = shutil.which("sox")

        if not os.path.exists(input_file):
            return {"error": "Input file not found", "simulated": True}

        if sox:
            try:
                proc = await asyncio.create_subprocess_exec(
                    sox, input_file, output_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=30.0)
                return {
                    "input_file": input_file,
                    "output_file": output_file,
                    "modulation": modulation,
                    "format": output_format,
                    "simulated": False,
                }
            except Exception as e:
                return {"error": str(e), "simulated": True}
        else:
            # Simulation: just copy the file
            import shutil as _shutil
            _shutil.copy2(input_file, output_file)
            return {
                "input_file": input_file,
                "output_file": output_file,
                "modulation": modulation,
                "format": output_format,
                "simulated": True,
            }

    # ── Digital Decode ────────────────────────────────────────────────────────

    async def decode_digital(
        self,
        input_file: str,
        protocol: str = "automatic",
    ) -> dict[str, Any]:
        """
        Decode digital protocols from a WAV/IQ file.
        Supports ADS-B (dump1090), POCSAG/APRS (multimon-ng), otherwise simulation.
        """
        dump1090 = shutil.which("dump1090")
        multimon = shutil.which("multimon-ng")

        if not os.path.exists(input_file):
            return self._simulated_decode(protocol)

        if protocol in ("ads-b", "automatic") and dump1090:
            try:
                proc = await asyncio.create_subprocess_exec(
                    dump1090, "--raw", "--ifile", input_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
                messages = [
                    line.strip()
                    for line in (stdout or b"").decode(errors="ignore").splitlines()
                    if line.strip()
                ]
                return {
                    "protocol": "ads-b",
                    "messages": messages,
                    "count": len(messages),
                    "simulated": False,
                }
            except Exception:
                pass

        if protocol in ("pocsag", "aprs", "automatic", "dtmf") and multimon:
            mode_flags: list[str] = []
            if protocol == "pocsag":
                mode_flags = ["-t", "POCSAG512", "-t", "POCSAG1200", "-t", "POCSAG2400"]
            elif protocol == "aprs":
                mode_flags = ["-t", "AFSK1200"]
            elif protocol == "dtmf":
                mode_flags = ["-t", "DTMF"]
            else:
                mode_flags = ["-t", "AFSK1200", "-t", "POCSAG1200", "-t", "DTMF"]

            try:
                proc = await asyncio.create_subprocess_exec(
                    multimon, "-a", *mode_flags, input_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
                messages = [
                    line.strip()
                    for line in (stdout or b"").decode(errors="ignore").splitlines()
                    if line.strip()
                ]
                return {
                    "protocol": protocol,
                    "messages": messages,
                    "count": len(messages),
                    "simulated": False,
                }
            except Exception:
                pass

        return self._simulated_decode(protocol)

    def _simulated_decode(self, protocol: str) -> dict[str, Any]:
        sims: dict[str, Any] = {
            "ads-b": {
                "protocol": "ads-b",
                "messages": [
                    "*8D4B18F4202CC371C39CE8EBEDAC;",
                    "*8D49F3C8F82300020049B81F8000;",
                    "*8DA4F2399901D514E804A5588A9E;",
                ],
                "aircraft": [
                    {"icao": "4B18F4", "callsign": "SWR123 ", "altitude": 35000, "speed": 480, "lat": 48.52, "lon": 9.14},
                    {"icao": "49F3C8", "callsign": "AFR456 ", "altitude": 28000, "speed": 510, "lat": 47.81, "lon": 8.70},
                ],
                "count": 3,
                "simulated": True,
            },
            "pocsag": {
                "protocol": "pocsag",
                "messages": [
                    "POCSAG1200: Address: 1234567 Function: 3 Alpha: TEST MESSAGE 1",
                    "POCSAG512: Address:  9876543 Function: 2 Numeric: 0123456789",
                ],
                "count": 2,
                "simulated": True,
            },
            "aprs": {
                "protocol": "aprs",
                "messages": [
                    "F5ZXX-9>APRS,WIDE1-1,WIDE2-1:!4823.00N/00220.00E>Mobile Station",
                    "F1ABC>APRS:@123456z4800.00N/00200.00E_270/010g015t072",
                ],
                "count": 2,
                "simulated": True,
            },
            "dtmf": {
                "protocol": "dtmf",
                "messages": ["DTMF: 1", "DTMF: 2", "DTMF: 3", "DTMF: #"],
                "count": 4,
                "simulated": True,
            },
        }
        default = {
            "protocol": protocol,
            "messages": [f"[SIM] No decoder available for protocol: {protocol}"],
            "count": 0,
            "simulated": True,
        }
        return sims.get(protocol, default)

    # ── Replay ────────────────────────────────────────────────────────────────

    async def replay_signal(
        self,
        input_file: str,
        frequency_mhz: float,
        gain: int = 40,
        repeat: int = 1,
    ) -> dict[str, Any]:
        """
        Replay a previously captured IQ file via HackRF.
        """
        hackrf_transfer = shutil.which("hackrf_transfer")

        if not os.path.exists(input_file):
            return {"error": "Input file not found", "simulated": True}

        if hackrf_transfer:
            freq_hz = int(frequency_mhz * 1e6)
            repeat_flag = str(max(repeat - 1, 0))
            cmd = [
                hackrf_transfer,
                "-t", input_file,
                "-f", str(freq_hz),
                "-s", "2000000",
                "-x", str(gain),
                "-R", repeat_flag,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=60.0 * repeat
                )
                success = proc.returncode == 0
                return {
                    "input_file": input_file,
                    "frequency_mhz": frequency_mhz,
                    "repeat": repeat,
                    "success": success,
                    "stderr": (stderr or b"").decode(errors="ignore")[:500],
                    "simulated": False,
                }
            except Exception as e:
                return {"error": str(e), "simulated": True}
        else:
            return {
                "input_file": input_file,
                "frequency_mhz": frequency_mhz,
                "repeat": repeat,
                "success": True,
                "simulated": True,
                "message": "Simulation only — HackRF hardware required for actual replay",
            }

    # ── Capture IQ ───────────────────────────────────────────────────────────

    async def capture_raw_iq(
        self,
        frequency_mhz: float,
        sample_rate: int = 2_000_000,
        gain: int = 40,
        duration: int = 5,
    ) -> dict[str, Any]:
        """
        Capture raw IQ samples from RTL-SDR or HackRF.
        """
        hw = await self.detect_hardware()
        rec_id = uuid.uuid4().hex[:8]
        output_file = str(_RECORDINGS_DIR / f"iq_{rec_id}.bin")
        freq_hz = int(frequency_mhz * 1e6)
        samples = sample_rate * duration

        rtl_sdr = shutil.which("rtl_sdr")
        hackrf_transfer = shutil.which("hackrf_transfer")

        if hw["rtlsdr"] and rtl_sdr:
            cmd = [
                rtl_sdr,
                "-f", str(freq_hz),
                "-s", str(sample_rate),
                "-g", str(gain),
                "-n", str(samples),
                output_file,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
                file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                return {
                    "recording_id": rec_id,
                    "frequency_mhz": frequency_mhz,
                    "sample_rate": sample_rate,
                    "duration": duration,
                    "file_path": output_file,
                    "file_size": file_size,
                    "simulated": False,
                    "hardware": "rtlsdr",
                }
            except Exception:
                pass

        if hw["hackrf"] and hackrf_transfer:
            cmd = [
                hackrf_transfer,
                "-r", output_file,
                "-f", str(freq_hz),
                "-s", str(sample_rate),
                "-l", str(gain),
                "-g", str(gain),
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
                file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
                return {
                    "recording_id": rec_id,
                    "frequency_mhz": frequency_mhz,
                    "sample_rate": sample_rate,
                    "duration": duration,
                    "file_path": output_file,
                    "file_size": file_size,
                    "simulated": False,
                    "hardware": "hackrf",
                }
            except Exception:
                pass

        # Simulation: write random IQ data
        iq_bytes = bytes(random.getrandbits(8) for _ in range(min(samples * 2, 1_000_000)))
        with open(output_file, "wb") as f:
            f.write(iq_bytes)
        return {
            "recording_id": rec_id,
            "frequency_mhz": frequency_mhz,
            "sample_rate": sample_rate,
            "duration": duration,
            "file_path": output_file,
            "file_size": len(iq_bytes),
            "simulated": True,
            "hardware": "simulation",
        }

    # ── Spectrum Analysis ─────────────────────────────────────────────────────

    async def analyze_spectrum(
        self,
        start_mhz: float,
        end_mhz: float,
        fft_size: int = 1024,
    ) -> dict[str, Any]:
        """
        Analyze spectrum and return band data + waterfall snapshot.
        """
        scan = await self.scan_frequencies(start_mhz=start_mhz, end_mhz=end_mhz)
        signals = scan.get("signals", [])

        # Build 64-column FFT row from signals
        num_cols = 64
        span = end_mhz - start_mhz

        def _power_row(noise_floor: float = -90.0) -> list[float]:
            row = [noise_floor + random.uniform(-3, 3) for _ in range(num_cols)]
            for sig in signals:
                f = sig["frequency_mhz"]
                if start_mhz <= f <= end_mhz:
                    col = int((f - start_mhz) / span * (num_cols - 1))
                    row[col] = max(row[col], sig["power_dbm"] + random.uniform(-2, 2))
                    # Spread
                    for d in range(1, 3):
                        if 0 <= col - d:
                            row[col - d] = max(row[col - d], sig["power_dbm"] - d * 8 + random.uniform(-3, 3))
                        if col + d < num_cols:
                            row[col + d] = max(row[col + d], sig["power_dbm"] - d * 8 + random.uniform(-3, 3))
            return row

        waterfall = [_power_row() for _ in range(5)]

        # Band summary
        band_width = span / 8
        bands: list[dict] = []
        for i in range(8):
            b_start = start_mhz + i * band_width
            b_end = b_start + band_width
            band_sigs = [s for s in signals if b_start <= s["frequency_mhz"] < b_end]
            peak = max((s["power_dbm"] for s in band_sigs), default=-90.0)
            bands.append({
                "start_mhz": round(b_start, 3),
                "end_mhz": round(b_end, 3),
                "peak_dbm": round(peak, 1),
                "signal_count": len(band_sigs),
            })

        strongest = sorted(signals, key=lambda x: x["power_dbm"], reverse=True)[:5]

        return {
            "start_mhz": start_mhz,
            "end_mhz": end_mhz,
            "fft_size": fft_size,
            "bands": bands,
            "waterfall_data": waterfall,
            "strongest_signals": strongest,
            "simulated": scan.get("simulated", True),
        }

    # ── Gate Remote Detection ─────────────────────────────────────────────────

    async def detect_gate_remote(
        self, frequency_mhz: float = 433.92
    ) -> dict[str, Any]:
        """
        Listen on 433.92 MHz (or specified freq) to capture gate/garage remote codes.
        """
        hw = await self.detect_hardware()
        rec_id = uuid.uuid4().hex[:8]
        output_wav = str(_RECORDINGS_DIR / f"gate_{rec_id}.wav")

        if (hw["rtlsdr"] or hw["hackrf"]) and shutil.which("rtl_fm"):
            result = await self.listen_frequency(
                frequency_mhz=frequency_mhz,
                duration=5,
                modulation="am",
                gain=40,
            )
            output_wav = result.get("file_path", output_wav)
            simulated = result.get("simulated", True)
        else:
            self._write_silent_wav(output_wav, 1)
            simulated = True

        # Simulate decoded codes
        captured_codes = [
            f"0x{random.randint(0, 0xFFFFFF):06X}" for _ in range(random.randint(2, 5))
        ] if simulated else []

        return {
            "frequency_mhz": frequency_mhz,
            "protocol_detected": "OOK" if simulated else "unknown",
            "raw_signal": output_wav,
            "captured_codes": captured_codes,
            "rolling_code": random.choice([True, False]),
            "modulation": "AM/OOK",
            "simulated": simulated,
            "note": "Simulation — no hardware available" if simulated else None,
        }

    # ── Jamming ───────────────────────────────────────────────────────────────

    async def jam_frequency(
        self,
        frequency_mhz: float,
        duration: int = 5,
    ) -> dict[str, Any]:
        """
        Transmit broadband noise on a frequency via HackRF.
        Returns simulation error if hardware is absent.
        """
        hackrf_transfer = shutil.which("hackrf_transfer")

        if not hackrf_transfer:
            return {
                "error": "Simulation only — HackRF hardware required for jamming",
                "frequency_mhz": frequency_mhz,
                "duration": duration,
                "simulated": True,
            }

        # Generate white-noise IQ file
        noise_file = str(_RECORDINGS_DIR / f"noise_{uuid.uuid4().hex[:8]}.bin")
        noise_size = 2_000_000 * 2  # 1s of noise at 2MSps
        noise_bytes = bytes(random.getrandbits(8) for _ in range(noise_size))
        with open(noise_file, "wb") as f:
            f.write(noise_bytes)

        freq_hz = int(frequency_mhz * 1e6)
        cmd = [
            hackrf_transfer,
            "-t", noise_file,
            "-f", str(freq_hz),
            "-s", "2000000",
            "-x", "47",
            "-R", str(duration - 1),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 10)
            return {
                "frequency_mhz": frequency_mhz,
                "duration": duration,
                "success": proc.returncode == 0,
                "stderr": (stderr or b"").decode(errors="ignore")[:300],
                "simulated": False,
            }
        except Exception as e:
            return {"error": str(e), "simulated": True}
        finally:
            try:
                os.unlink(noise_file)
            except OSError:
                pass

    # ── Simulation Helpers ────────────────────────────────────────────────────

    def _simulation_scan(self, start_mhz: float, end_mhz: float) -> dict[str, Any]:
        """Generate a realistic simulated spectrum scan."""
        signals: list[dict] = []
        step = max((end_mhz - start_mhz) / 200, 0.01)
        freq = start_mhz
        while freq <= end_mhz:
            power = -90.0 + random.uniform(-3, 3)
            # Check proximity to known peaks
            for peak_mhz in _KNOWN_FREQS:
                delta = abs(freq - peak_mhz)
                if delta < 0.05:
                    boost = max(0, 45 - (delta / 0.05) * 45)
                    power = max(power, -45.0 + boost + random.uniform(-2, 2))
                elif delta < 0.2:
                    boost = max(0, 15 - (delta / 0.2) * 15)
                    power = max(power, -70.0 + boost + random.uniform(-3, 3))
            signals.append({
                "frequency_mhz": round(freq, 3),
                "power_dbm": round(power, 1),
            })
            freq += step

        peaks = sorted(signals, key=lambda x: x["power_dbm"], reverse=True)[:5]
        return {
            "start_mhz": start_mhz,
            "end_mhz": end_mhz,
            "signals": signals,
            "peaks": peaks,
            "simulated": True,
            "hardware": "simulation",
        }

    def get_simulation_mode(self) -> bool:
        """Synchronous check: are we in simulation mode (no hardware)?"""
        hackrf = bool(shutil.which("hackrf_info"))
        rtlsdr = bool(shutil.which("rtl_test"))
        bladerf = bool(shutil.which("bladeRF-cli"))
        return not (hackrf or rtlsdr or bladerf)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _write_silent_wav(path: str, duration_s: int = 1) -> None:
        """Write a minimal silent WAV file (PCM 16-bit, 48kHz, mono)."""
        sample_rate = 48000
        n_samples = sample_rate * max(duration_s, 1)
        data_size = n_samples * 2  # 16-bit = 2 bytes per sample
        with open(path, "wb") as f:
            # RIFF header
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            # fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
            # data chunk
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(b"\x00" * data_size)
