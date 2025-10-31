import asyncio, time
import pytest
from rally_audio import audio_scheduler
from rally_store import rally_store, RALLY_PREP_SECONDS

@pytest.mark.asyncio
async def test_audio_update_and_schedule(monkeypatch):
    # ensure disabled initial
    state = await audio_scheduler.get_state()
    # set minimal config
    await audio_scheduler.update_config(enabled=True, sound_name='', lead_seconds=10, offset_ms=50)
    # create player & rally to produce earliest landing
    import uuid
    # Add player
    pid = (await rally_store.create_player('TestP', 120, 120))['player_id']
    now = int(time.time())
    # created_ts so launch in 100s (bounded) = now+100-300 => clamp to now (store clamps future) so keep near now
    rid = (await rally_store.create_rally(pid, now))['rally_id']
    # Force recompute
    await audio_scheduler.recompute_now_for_test()
    st2 = await audio_scheduler.get_state()
    # Should have next_landing_ts > 0 when enabled and rally exists
    assert st2['next_landing_ts'] >= now
    # Offset update
    old_offset = st2['offset_ms']
    await audio_scheduler.adjust_offset_ms(5)
    st3 = await audio_scheduler.get_state()
    assert st3['offset_ms'] == old_offset + 5
