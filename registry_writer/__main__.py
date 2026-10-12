# registry_writer/__main__.py — daemon entrypoint (systemd / operator)
#
# Usage:
#   python -m registry_writer --config config/registry-writer.yaml
#   python -m registry_writer --root <tmp> --socket ipc.sock \
#       --secret <path> [--group dsh] [--mode 0660]   # sandbox/tests
#
# If started as root, privileges are dropped to the configured uid/gid
# (dsh-writer) after config load + secret read + socket bind (defense in
# depth — the FINAL architecture §4.2 requirement).
#
# The daemon is fail-closed at startup: an unwritable/missing root or secret
# raises INTERNAL_ERROR and the process exits non-zero (never starts degraded).

from __future__ import annotations

import argparse
import os
import signal
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _load_config_file(path: str) -> dict:
    import yaml
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="registry_writer",
                                     description="G10 O3 registry writer daemon")
    parser.add_argument("--config", help="YAML config file (config/registry-writer.yaml)")
    parser.add_argument("--root", help="daemon root (overrides config)")
    parser.add_argument("--socket", help="socket path (overrides config)")
    parser.add_argument("--secret", help="HMAC secret path (overrides config)")
    parser.add_argument("--group", help="socket group (default dsh)")
    parser.add_argument("--mode", help="socket mode octal (default 0660)")
    args = parser.parse_args(argv)

    # Build config from file, then apply CLI overrides.
    file_cfg = _load_config_file(args.config) if args.config else {}
    daemon_cfg = file_cfg.get("daemon", {})
    auth_cfg = file_cfg.get("auth", {})
    limits_cfg = file_cfg.get("limits", {})

    root = args.root or daemon_cfg.get("root")
    socket_path = args.socket or daemon_cfg.get("socket_path")
    secret_path = args.secret or auth_cfg.get("hmac_secret_path")
    if not (root and socket_path and secret_path):
        print("error: root, socket_path and hmac_secret_path are required",
              file=sys.stderr)
        return 2

    from registry_writer.daemon import DaemonConfig
    config = DaemonConfig(
        root=root,
        socket_path=socket_path,
        pid_file=daemon_cfg.get("pid_file", "daemon.pid"),
        uid=daemon_cfg.get("uid", "dsh-writer"),
        gid=daemon_cfg.get("gid", "dsh-writer"),
        socket_group=args.group or daemon_cfg.get("socket_group", "dsh"),
        socket_mode=(
                int(args.mode, 8)
                if args.mode
                else (
                    int(daemon_cfg.get("socket_mode", "0660"), 8)
                    if isinstance(daemon_cfg.get("socket_mode", "0660"), str)
                    else int(daemon_cfg.get("socket_mode", 0o660))
                )
            ),
        hmac_secret_path=secret_path,
        replay_window_seconds=int(auth_cfg.get("replay_window_seconds", 30)),
        backup_dir=daemon_cfg.get("backup_dir", ""),
        max_doc_bytes=int(limits_cfg.get("max_doc_bytes", 16 * 1024 * 1024)),
        max_payload_bytes=int(limits_cfg.get("max_payload_bytes", 32 * 1024 * 1024)),
        connection_limit=int(limits_cfg.get("connection_limit", 64)),
        request_timeout_seconds=int(limits_cfg.get("request_timeout_seconds", 30)),
        graceful_shutdown_seconds=int(limits_cfg.get("graceful_shutdown_seconds", 10)),
    )

    # Optional privilege drop: only relevant when started as root.
    if os.geteuid() == 0:
        try:
            import grp, pwd
            gid = grp.getgrnam(config.gid).gr_gid
            uid = pwd.getpwnam(config.uid).pw_uid
            os.setgroups([gid])
            os.setgid(gid)
            os.setuid(uid)
        except (KeyError, OSError) as e:
            print(f"error: privilege drop to {config.uid}:{config.gid} failed: {e}",
                  file=sys.stderr)
            return 1

    from registry_writer.daemon import run_daemon

    # run_daemon() blocks inside the accept loop, so the stop handler MUST be
    # registered before it runs: previously the signal.signal() calls and the
    # keep-alive wait below sat *after* run_daemon() and were unreachable dead
    # code, so a SIGTERM killed the process with no graceful shutdown, no
    # thread join and no socket unlink.
    _daemon: dict = {}

    def _stop(_sig, _frame):
        daemon = _daemon.get("daemon")
        if daemon is not None:
            daemon.shutdown()  # joins handlers, unlinks the socket
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Blocks until shutdown() is called (normally from _stop above).
    daemon = run_daemon(config)
    _daemon["daemon"] = daemon
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
