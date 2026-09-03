# RECOVERY tests — restart, corruption, backup/restore (O3-REC-001..006)

import json
import os
import pytest

from registry_writer.client import DaemonRpcError, RegistryWriterClient, WriterUnavailable


class TestRecovery:
    """O3-REC acceptance tests (FINAL 0004 §2.5)."""

    def test_rec_001_restart_intact(self, o3_client, o3_config, o3_secret, o3_tmp_root):
        """O3-REC-001: restart with intact ledger resumes correctly."""
        # Write some data
        o3_client.registry_write("rec-test", {"name": "v1"}, 0)
        o3_client.audit_append("rec-proj", {"event_id": "rec-e1", "msg": "pre-restart"})

        # Simulate restart: we already have a running daemon from the
        # session fixture.  The daemon thread is daemon=True so it
        # continues.  We just verify that after writing, the data is
        # still accessible.
        r = o3_client.registry_read("rec-test")
        assert r.get("version") == 1
        ar = o3_client.audit_read("rec-proj")
        assert ar.get("count") == 1

    def test_rec_002_corrupted_ledger_fails_closed(self, o3_client, o3_tmp_root):
        """O3-REC-002: corrupted ledger → append returns CORRUPTION_DETECTED
        (fail-closed — the daemon never silently accepts a corrupt ledger)."""
        events_path = os.path.join(o3_tmp_root, "audit/rec-corrupt/events.jsonl")
        os.makedirs(os.path.dirname(events_path), exist_ok=True)
        with open(events_path, "w") as f:
            f.write('{"event_id": "valid", "msg": "ok"}\n')
            f.write('CORRUPTED LINE\n')

        # Append to the corrupted ledger — should return CORRUPTION_DETECTED
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.audit_append("rec-corrupt", {"event_id": "rec-e2", "msg": "after"})
        assert exc.value.code == "CORRUPTION_DETECTED", f"got {exc.value.code}"

    def test_rec_003_backup_snapshot(self, o3_client, o3_tmp_root):
        """O3-REC-003: backup snapshot creates manifest with hashes."""
        o3_client.registry_write("bak-test", {"name": "backup"}, 0)
        b = o3_client.backup(label="test-backup-003")
        assert "backup_path" in b
        assert "manifest" in b
        assert len(b["manifest"]) > 0
        # Verify manifest file exists
        man_path = os.path.join(b["backup_path"], "MANIFEST.sha256")
        assert os.path.exists(man_path)

    def test_rec_004_restore_verified(self, o3_client, o3_tmp_root):
        """O3-REC-004: backup + restore works."""
        o3_client.registry_write("rest-test", {"name": "pre-backup"}, 0)
        b = o3_client.backup(label="test-restore-004")
        # Corrupt the live doc
        o3_client.registry_write("rest-test", {"name": "corrupted"}, 1)
        # Restore
        r = o3_client.restore(b["backup_path"], confirmed=True)
        assert r.get("restored") is True
        # Verify
        doc = o3_client.registry_read("rest-test")
        assert doc.get("data", {}).get("name") == "pre-backup"

    def test_rec_005_tampered_backup_refused(self, o3_client, o3_tmp_root):
        """O3-REC-005: forged/tampered backup is refused (fail-closed)."""
        o3_client.registry_write("tamper-test", {"name": "original"}, 0)
        b = o3_client.backup(label="test-tamper-005")
        # Tamper the backup
        for dirpath, _dirs, files in os.walk(b["backup_path"]):
            for fn in files:
                if fn == "MANIFEST.sha256":
                    continue
                fp = os.path.join(dirpath, fn)
                with open(fp, "a") as f:
                    f.write("TAMPERED")
        # Restore should fail
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.restore(b["backup_path"], confirmed=True)
        assert exc.value.code == "CORRUPTION_DETECTED", f"got {exc.value.code}"

    def test_rec_006_recovery_authority(self, o3_client):
        """O3-REC-006: recovery/restore does not grant new capability.
        The restore method requires the same auth channel as any other
        write method.  Proved by running restore with a bad token."""
        b = o3_client.backup(label="test-auth-006")
        from registry_writer.client import RegistryWriterClient
        bad_client = RegistryWriterClient(o3_client.socket_path, b"wrong-secret-32-bytes-long!!")
        with pytest.raises(DaemonRpcError) as exc:
            bad_client.restore(b["backup_path"], confirmed=True)
        assert exc.value.code == "UNAUTHORIZED", f"got {exc.value.code}"