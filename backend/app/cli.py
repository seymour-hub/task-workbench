from __future__ import annotations

import argparse
import json
import sys

from .db import init_db, session_scope
from .services.file_service import scan_all
from .services.notify_service import send_digest, test_send


def _print(data) -> None:
    if isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(prog="workbench", description="任务管理工作台 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="初始化数据库")

    sync_parser = sub.add_parser("sync", help="同步 Hermes 会话")
    sync_parser.add_argument("--full", action="store_true", help="从头回填全部消息")
    sync_parser.add_argument("--days", type=int, default=None, help="回填天数")

    extract_parser = sub.add_parser("extract", help="对片段执行 AI 抽取")
    extract_parser.add_argument("--limit", type=int, default=5)
    extract_parser.add_argument("--force", action="store_true")

    sub.add_parser("scan-files", help="扫描交付物根目录")
    sub.add_parser("digest", help="立即生成并发送日报")
    sub.add_parser("dedupe-inbox", help="标记收件箱中的重复任务候选")
    sub.add_parser("cleanup-deliverables", help="清理过程脚本/临时文件并重算最终版")
    merge_parser = sub.add_parser("merge-tasks", help="把过程任务合并成一个项目级任务")
    merge_parser.add_argument("--target", type=int, required=True)
    merge_parser.add_argument("--sources", required=True, help="逗号分隔的任务 id")
    merge_parser.add_argument("--note", default=None)
    sub.add_parser("status", help="查看同步与抽取状态")

    notify_parser = sub.add_parser("test-notify", help="发送飞书测试通知")
    notify_parser.add_argument("--text", default=None)

    args = parser.parse_args()
    init_db()

    if args.command == "init":
        _print({"ok": True, "message": "数据库已初始化"})
        return 0

    with session_scope() as db:
        if args.command == "sync":
            from .ingest.sync_service import sync_now

            _print(sync_now(db, backfill_days=args.days, full=args.full))
        elif args.command == "extract":
            from .ai.extractor import extract_pending

            _print(extract_pending(db, limit=args.limit, force=args.force))
        elif args.command == "scan-files":
            from .db import get_int_setting

            _print(scan_all(db, max_files=get_int_setting(db, "files.max_files_per_root", 20_000)))
        elif args.command == "digest":
            _print(send_digest(db))
        elif args.command == "dedupe-inbox":
            from .ai.deduper import dedupe_pending

            _print(dedupe_pending(db))
        elif args.command == "cleanup-deliverables":
            from .services.deliverable_service import cleanup_existing

            _print(cleanup_existing(db))
        elif args.command == "merge-tasks":
            from .services.task_service import merge_tasks

            source_ids = [int(value) for value in args.sources.split(",") if value.strip()]
            _print(merge_tasks(db, args.target, source_ids, note=args.note))
        elif args.command == "test-notify":
            _print(test_send(db, args.text))
        elif args.command == "status":
            from .ingest.sync_service import sync_status

            _print(sync_status(db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
