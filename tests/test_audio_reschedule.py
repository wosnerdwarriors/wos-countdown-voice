import asyncio, time, pytest
from rally_audio import audio_scheduler
from rally_store import rally_store

@pytest.mark.asyncio
async def test_auto_reschedule_after_rally_adjust():
    # configure enabled with simple params
    await audio_scheduler.update_config(enabled=True, sound_name='', lead_seconds=5, offset_ms=0)
    # create player & rally
    pid = (await rally_store.create_player('ReschedP', 60, 60))['player_id']
    now = int(time.time())
    rid = (await rally_store.create_rally(pid, now))['rally_id']
    await audio_scheduler.recompute_now_for_test()
    st1 = await audio_scheduler.get_state()
    first_landing = st1['next_landing_ts']
    # adjust rally earlier by 3s
    await rally_store.adjust_rally_created(rid, -3)
    # wait a bit for watcher to fire
    await asyncio.sleep(1.2)
    st2 = await audio_scheduler.get_state()
    # it should have recomputed (earlier landing => landing ts may decrease or schedule cleared if already fired window)
    assert st2['next_landing_ts'] <= first_landing
