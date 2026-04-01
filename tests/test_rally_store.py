import os, tempfile, asyncio, time
import unittest
from rally_store import RallyStore, RALLY_PREP_SECONDS, PET_ACTIVE_SECONDS, DataValidationError

class RallyStoreTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_path = os.path.join(self.tmpdir.name, 'test-data.json')
        # ensure env not interfering
        self.store = RallyStore(data_file=self.data_path)

    async def asyncTearDown(self):
        self.tmpdir.cleanup()

    async def test_player_create_update_delete(self):
        res = await self.store.create_player('Alice', 100, 80, pet_status='none')
        pid = res['player_id']
        snap = await self.store.snapshot()
        self.assertIn(pid, snap['players'])
        await self.store.update_player(pid, name='Alicia')
        snap2 = await self.store.snapshot()
        self.assertEqual(snap2['players'][pid]['name'], 'Alicia')
        await self.store.delete_player(pid)
        snap3 = await self.store.snapshot()
        self.assertNotIn(pid, snap3['players'])

    async def test_rally_create_and_adjust_bounds(self):
        pid = (await self.store.create_player('Bob', 120, 100))['player_id']
        now = int(time.time())
        # create at now
        rid = (await self.store.create_rally(pid, now))['rally_id']
        # adjust older beyond window should clamp
        await self.store.adjust_rally_created(rid, -(RALLY_PREP_SECONDS + 50))
        snap = await self.store.snapshot()
        created = snap['rallies'][rid]['created_ts']
        self.assertGreaterEqual(created, int(time.time()) - RALLY_PREP_SECONDS - 1)
        # adjust into future should clamp to now
        await self.store.adjust_rally_created(rid, 1000)
        snap2 = await self.store.snapshot()
        self.assertLessEqual(snap2['rallies'][rid]['created_ts'], int(time.time()) + 1)

    async def test_arrival_pattern(self):
        p1 = (await self.store.create_player('P1', 60, 40))['player_id']
        now = int(time.time())
        await self.store.create_rally(p1, now)
        pat = await self.store.arrival_pattern()
        self.assertEqual(len(pat['entries']), 1)
        self.assertEqual(pat['pattern'], [0])

    async def test_pet_expiration(self):
        # activate pet but simulate expiry
        pid = (await self.store.create_player('PetUser', 120, 90, pet_status='active', pet_activated_at=int(time.time()) - PET_ACTIVE_SECONDS - 10))['player_id']
        snap = await self.store.snapshot()
        self.assertEqual(snap['players'][pid]['pet_status'], 'expired')

    async def test_events_sequence(self):
        start_seq = (await self.store.snapshot())['seq']
        pid = (await self.store.create_player('E1', 50, 40))['player_id']
        after_seq = (await self.store.snapshot())['seq']
        self.assertGreater(after_seq, start_seq)
        # wait_for_events should return immediately with newer seq
        seq, events = await self.store.wait_for_events(after_seq - 1, timeout=1)
        self.assertTrue(any(e.get('type') == 'player.create' for e in events))

    async def test_wait_timeout(self):
        seq_before = (await self.store.snapshot())['seq']
        seq, events = await self.store.wait_for_events(seq_before, timeout=1)
        self.assertEqual(seq, seq_before)
        self.assertEqual(events, [])

if __name__ == '__main__':
    unittest.main()
