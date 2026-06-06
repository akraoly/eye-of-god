"""Tests CobaltStrikeC2 — External C2 Protocol."""
from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from c2_manager.integrations.cobalt_strike import CobaltStrikeC2
from c2_manager.interfaces.external_c2 import (
    pack_frame, unpack_frame, FRAME_STAGE, FRAME_TASK, FRAME_RESPONSE, FRAME_PING,
)
from c2_manager.models import C2Config, C2Type, C2Status


@pytest.fixture
def cs():
    return CobaltStrikeC2()


class TestExternalC2Protocol:
    def test_pack_frame_stage(self):
        data  = b"hello beacon"
        frame = pack_frame(FRAME_STAGE, data)
        assert len(frame) == 4 + 1 + len(data)
        assert frame[4] == FRAME_STAGE
        length = struct.unpack(">I", frame[:4])[0]
        assert length == len(data)

    def test_pack_frame_task(self):
        data  = b"shell whoami"
        frame = pack_frame(FRAME_TASK, data)
        assert frame[4] == FRAME_TASK

    def test_unpack_frame_stage(self):
        data  = b"stage_data"
        frame = pack_frame(FRAME_STAGE, data)
        ftype, unpacked = unpack_frame(frame)
        assert ftype   == FRAME_STAGE
        assert unpacked == data

    def test_unpack_frame_response(self):
        data  = b"beacon response"
        frame = pack_frame(FRAME_RESPONSE, data)
        ftype, unpacked = unpack_frame(frame)
        assert ftype   == FRAME_RESPONSE
        assert unpacked == data

    def test_unpack_short_buffer_raises(self):
        with pytest.raises(ValueError):
            unpack_frame(b"\x00\x00")

    def test_pack_unpack_roundtrip(self):
        for ftype in (FRAME_STAGE, FRAME_TASK, FRAME_RESPONSE, FRAME_PING):
            data  = b"roundtrip test data " + bytes([ftype])
            frame = pack_frame(ftype, data)
            t, d  = unpack_frame(frame)
            assert t == ftype
            assert d == data


class TestCobaltStrikeBeaconRegistry:
    def test_register_beacon_from_stage(self, cs):
        # Créer un stage avec beacon_id = 0xDEADBEEF
        stage = struct.pack("<I", 0xDEADBEEF) + b"\x01"  # x64 indicator
        cs._register_beacon(stage)
        assert "3735928559" in cs._beacons
        assert cs._beacons["3735928559"]["arch"] == "x64"

    def test_register_beacon_x86(self, cs):
        stage = struct.pack("<I", 42) + b"\x00"  # x86
        cs._register_beacon(stage)
        assert cs._beacons["42"]["arch"] == "x86"

    def test_extract_beacon_id(self, cs):
        data = struct.pack("<I", 12345) + b"response_data"
        bid  = cs._extract_beacon_id(data)
        assert bid == "12345"

    def test_extract_beacon_id_short_data(self, cs):
        bid = cs._extract_beacon_id(b"\x01\x02")
        assert bid == "unknown"


class TestCobaltStrikeTasks:
    @pytest.mark.asyncio
    async def test_send_task_external_c2_queues(self, cs, cobalt_strike_config):
        cs._config = cobalt_strike_config
        cs._status = C2Status.CONNECTED
        cs._writer = AsyncMock()
        cs._writer.is_closing.return_value = False

        task = await cs.send_task("12345", "shell", ["whoami"])
        assert task.status in ("queued", "sent")
        assert not cs._pending_tasks.empty()

    @pytest.mark.asyncio
    async def test_get_task_result_empty_queue(self, cs, cobalt_strike_config):
        cs._config = cobalt_strike_config
        result = await cs.get_task_result("task-123")
        assert result["task_id"] == "task-123"
        assert "responses" in result


class TestCobaltStrikeCapabilities:
    @pytest.mark.asyncio
    async def test_get_capabilities(self, cs):
        caps = await cs.get_capabilities()
        assert "external_c2" in caps
        assert "beacon_staging" in caps
