#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DY-AI_TOWN 世界工程同步工具（造世界 / AI World Creator）

四个子命令：
  verify   按 项目清单.json 校验所有文件的 size + sha256，并检查仓库卫生（只读）
  install  把仓库里的工程复制进编辑器数据目录，并在 projects.json 登记
  link     不复制，直接把仓库里的工程路径登记进 projects.json（git 工作区即工程目录）
  sync     git pull 之后，把仓库工程覆盖到已登记的本机路径（保留运行时产物）

只依赖标准库，支持 Windows / macOS。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

PROJECT_ID = "project_vqo1bvzh"
# 一个工程里真正属于"资产"的条目，sync 时只动这几个，运行时产物不碰
PROJECT_ITEMS = ["project.json", "scene.data", "world-config.json", "settings", "scripts"]
MANIFEST_NAME = "项目清单.json"
EDITOR_DIRNAME = "造世界编辑器"      # Electron 用户数据目录（读账号 uid 用）
DATA_DIRNAME = "AI World Creator"    # 编辑器业务数据目录（projects 在这里）

# 这些文件/目录永远不该进仓库
FORBIDDEN_NAMES = {"projects.json"}
FORBIDDEN_DIRS = {".creator"}
FORBIDDEN_SUFFIX = (".bak",)
FORBIDDEN_PREFIX = ("shot.",)
AI_CONFIG_NAMES = {
    "ai-asset-generate-config.json",
    "ai-pcg-generate-config.json",
    "ai-topology-generate-config.json",
}


# ---------------------------------------------------------------- 基础工具

def die(msg: str, code: int = 1) -> "None":
    print(f"❌ {msg}")
    sys.exit(code)


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def info(msg: str) -> None:
    print(f"ℹ️  {msg}")


def warn(msg: str) -> None:
    print(f"⚠️  {msg}")


def stamp() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def support_dir() -> Path:
    """返回编辑器的支持目录：Windows 是 %APPDATA%，macOS 是 ~/Library/Application Support"""
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support"
    appdata = os.environ.get("APPDATA")
    if not appdata:
        die("拿不到 %APPDATA%，无法定位编辑器目录。用 --target 手动指定。")
    return Path(appdata)


def data_root(target: str | None) -> Path:
    """编辑器业务数据根目录（其下有 projects/）"""
    if target:
        return Path(target).expanduser().resolve()
    return support_dir() / DATA_DIRNAME


# ---------------------------------------------------------------- projects.json

def records_path(root: Path) -> Path:
    return root / "projects" / "projects.json"


def load_records(root: Path) -> list:
    p = records_path(root)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"projects.json 解析失败（{p}）：{e}")
    if isinstance(data, dict):
        data = [data]
    return [r for r in data if isinstance(r, dict)]


def save_records(root: Path, records: list, dry_run: bool) -> None:
    p = records_path(root)
    if dry_run:
        info(f"[dry-run] 将写入 {p}")
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        backup = p.with_name(f"{p.name}.bak-{stamp()}")
        shutil.copy2(p, backup)
        info(f"已备份原 projects.json → {backup.name}")
    payload = json.dumps(records, ensure_ascii=False, indent=2)
    # 显式 UTF-8 无 BOM，避免编辑器读不出来
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(payload + "\n")
    ok(f"已更新 {p}")


def normalize(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


def register(root: Path, project_path: Path, uid: str, dry_run: bool) -> None:
    """在 projects.json 里登记（去重），latestOpenTime/latestEditTime 用当前时间"""
    records = load_records(root)
    now = int(time.time() * 1000)
    project_path = project_path.expanduser().resolve()
    kept = [r for r in records if normalize(r.get("projectPath", "")) != normalize(str(project_path))]
    kept.append({
        "projectPath": str(project_path),
        "latestOpenTime": now,
        "latestEditTime": now,
        "uid": uid,
    })
    save_records(root, kept, dry_run)


# ---------------------------------------------------------------- uid

def uid_from_editor_config() -> str | None:
    """从编辑器自己的 config.json 读当前登录账号 uid —— 这是唯一可靠来源"""
    p = support_dir() / EDITOR_DIRNAME / "config.json"
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    uid = (cfg.get("userinfo") or {}).get("uid")
    return str(uid) if uid else None


def resolve_uid(explicit: str | None, root: Path) -> str:
    """
    优先级：--uid → 编辑器 config.json 的 userinfo.uid → 已有记录里的 uid → 报错。
    绝不回退到打包者的 uid：那会把别人的账号写进成员本机。
    """
    if explicit:
        return str(explicit)
    uid = uid_from_editor_config()
    if uid:
        return uid
    for r in load_records(root):
        if r.get("uid"):
            return str(r["uid"])
    die("拿不到你的账号 uid。请先打开一次造世界编辑器并登录，或用 --uid 手动指定。\n"
        "   （老版安装脚本在这里会回退到打包者的 uid，那是错的，本工具故意不这么做。）")


# ---------------------------------------------------------------- verify

# 这些属于仓库管道，改得频繁且不是资产，不进清单
MANIFEST_SKIP = {".gitignore", ".gitattributes", MANIFEST_NAME}
MANIFEST_SKIP_DIRS = {".git", ".github"}


def collect_files(repo: Path) -> list:
    out = []
    for p in sorted(repo.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(repo)
        if rel.parts and rel.parts[0] in MANIFEST_SKIP_DIRS:
            continue
        if rel.as_posix() in MANIFEST_SKIP or rel.name in MANIFEST_SKIP:
            continue
        out.append(rel.as_posix())
    return out


def read_manifest(repo: Path) -> dict:
    p = repo / MANIFEST_NAME
    if not p.exists():
        die(f"找不到 {MANIFEST_NAME}，先在仓库根目录运行 verify --update-manifest 生成。")
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_verify(args) -> int:
    repo = Path(args.repo).resolve()
    manifest = read_manifest(repo)
    entries = {e["path"]: e for e in manifest.get("文件", [])}

    problems = []
    checked = 0
    for rel, entry in sorted(entries.items()):
        f = repo / rel
        if not f.exists():
            problems.append({"path": rel, "issue": "missing"})
            continue
        size = f.stat().st_size
        if size != entry.get("size"):
            problems.append({"path": rel, "issue": "size", "expected": entry.get("size"), "actual": size})
            continue
        digest = sha256_of(f)
        if digest != entry.get("sha256"):
            problems.append({"path": rel, "issue": "sha256", "expected": entry.get("sha256")[:12], "actual": digest[:12]})
            continue
        checked += 1

    # 仓库卫生：不该出现的文件
    hygiene = []
    if not args.no_hygiene:
        for rel in collect_files(repo):
            name = Path(rel).name
            parts = set(Path(rel).parts)
            if name in FORBIDDEN_NAMES:
                hygiene.append({"path": rel, "issue": "禁止提交 projects.json（含本机 uid）"})
            elif name in AI_CONFIG_NAMES:
                hygiene.append({"path": rel, "issue": "编辑器运行时生成，不应入库"})
            elif name in FORBIDDEN_DIRS or FORBIDDEN_DIRS & parts:
                hygiene.append({"path": rel, "issue": ".creator/ 是运行目录，不应入库"})
            elif ".bak-" in name or name.endswith(FORBIDDEN_SUFFIX):
                hygiene.append({"path": rel, "issue": "备份文件不应入库"})
            elif name.startswith(FORBIDDEN_PREFIX):
                hygiene.append({"path": rel, "issue": "临时截图不应入库"})

    # 结构完整性
    structure = []
    proj = repo / "projects" / PROJECT_ID
    if not proj.is_dir():
        structure.append({"path": f"projects/{PROJECT_ID}", "issue": "工程目录缺失"})
    else:
        for item in PROJECT_ITEMS:
            if not (proj / item).exists():
                structure.append({"path": f"projects/{PROJECT_ID}/{item}", "issue": "工程必需条目缺失"})

    failed = bool(problems or hygiene or structure)
    if args.json:
        print(json.dumps({
            "repo": str(repo),
            "checked": checked,
            "manifest_entries": len(entries),
            "problems": problems,
            "hygiene": hygiene,
            "structure": structure,
            "ok": not failed,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"仓库：{repo}")
        print(f"清单条目 {len(entries)} 条，通过 {checked} 条")
        for p in problems:
            print(f"  ❌ {p['path']}  [{p['issue']}] {p.get('expected','')} → {p.get('actual','')}")
        for h in hygiene:
            print(f"  🚫 {h['path']}  {h['issue']}")
        for s in structure:
            print(f"  ❌ {s['path']}  {s['issue']}")
        if failed:
            print("\n结论：校验失败。修好上面的问题再提交。")
        else:
            ok("校验通过：所有文件与清单一致，仓库干净。")

    if args.update_manifest:
        # 以当前磁盘内容为准重建清单：这是"我确实改了资产"的显式确认动作，
        # 所以即使存在 drift 也照常重建，只把 drift 打印出来供人核对。
        if problems:
            warn(f"检测到 {len(problems)} 处与旧清单不一致，已按当前文件重建清单（请确认这些改动是有意的）")
        normalize_newlines(repo)
        write_manifest(repo, manifest)
        ok(f"已刷新 {MANIFEST_NAME}（{len(read_manifest(repo).get('文件', []))} 条）")
        return 0

    if failed:
        return 1
    return 0


def write_manifest(repo: Path, old: dict) -> None:
    files = []
    for rel in collect_files(repo):
        f = repo / rel
        files.append({
            "path": rel,
            "size": f.stat().st_size,
            "sha256": sha256_of(f),
        })
    files.sort(key=lambda x: x["path"])
    manifest = {
        "包名": old.get("包名", "DY-AI_TOWN"),
        "工程": PROJECT_ID,
        "worldId": old.get("worldId"),
        "编辑器版本": old.get("编辑器版本", "1.0.92"),
        "文件数": len(files),
        "总体积": sum(x["size"] for x in files),
        "说明": "改动资产后必须运行 python tools/world.py verify --update-manifest 刷新本清单；"
                "world-config.json 中的 quickPreview（原作者快速预览二维码）已移除。",
        "文件": files,
    }
    p = repo / MANIFEST_NAME
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------- 换行符归一

TEXT_LF_EXT = {".json", ".md", ".py", ".lua", ".txt", ".yml", ".yaml", ".command", ".sh"}
TEXT_CRLF_EXT = {".ps1", ".bat", ".cmd"}
TEXT_NO_EXT = {"LICENSE", "NOTICE", "AUTHORS"}
BINARY_EXT = {".data", ".png", ".jpg", ".jpeg", ".zip"}


def normalize_newlines(repo: Path, quiet: bool = False) -> list:
    """
    按 .gitattributes 的约定统一换行符：
      文本 → LF（.ps1/.bat/.cmd 例外，保持 CRLF）
      二进制 → 不碰
    为什么必须做：git 提交时会按 .gitattributes 规范化换行，
    而清单是按工作区文件算哈希的。Windows 上若工作区是 CRLF、仓库里是 LF，
    CI 一 clone 就会报 sha256 不一致。这里提前对齐，省掉这类假失败。
    """
    changed = []
    for rel in collect_files(repo):
        p = repo / rel
        ext = p.suffix.lower()
        name = p.name
        if ext in BINARY_EXT:
            continue
        if ext in TEXT_LF_EXT or (not ext and name in TEXT_NO_EXT):
            target = b"\n"
        elif ext in TEXT_CRLF_EXT:
            target = b"\r\n"
        else:
            continue
        raw = p.read_bytes()
        if b"\x00" in raw[:4096]:      # 保险：看着像二进制就别动
            continue
        unified = raw.replace(b"\r\n", b"\n")
        if target == b"\r\n":
            unified = unified.replace(b"\n", b"\r\n")
        if unified != raw:
            p.write_bytes(unified)
            changed.append(rel)
    if changed and not quiet:
        info(f"已统一 {len(changed)} 个文件的换行符：" + "、".join(changed))
    return changed


def cmd_normalize(args) -> int:
    repo = Path(args.repo).resolve()
    changed = normalize_newlines(repo)
    if not changed:
        ok("所有文本文件换行符已符合 .gitattributes，无需改动。")
    return 0


# ---------------------------------------------------------------- install / link / sync

def cmd_install(args) -> int:
    repo = Path(args.repo).resolve()
    root = data_root(args.target)
    src = repo / "projects" / PROJECT_ID
    if not src.is_dir():
        die(f"仓库里找不到工程目录：{src}")

    uid = resolve_uid(args.uid, root)
    dest = root / "projects" / PROJECT_ID

    print(f"仓库工程：{src}")
    print(f"安装目标：{dest}")
    print(f"本机账号：{uid}")

    if dest.exists():
        backup = dest.with_name(f"{PROJECT_ID}.bak-{stamp()}")
        if args.dry_run:
            info(f"[dry-run] 将把已存在的工程改名备份为 {backup.name}")
        else:
            dest.rename(backup)
            info(f"已存在的工程已备份为 {backup.name}")

    if args.dry_run:
        info(f"[dry-run] 将复制 {src} → {dest}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        ok(f"工程已复制到 {dest}")

    register(root, dest, uid, args.dry_run)
    if not args.dry_run:
        print()
        ok("安装完成。重新打开编辑器，项目列表里就有「糖果童趣小镇（主世界）」。")
    return 0


def cmd_link(args) -> int:
    """不复制，直接登记仓库内的工程路径；适合把 clone 目录当工作区用的人"""
    repo = Path(args.repo).resolve()
    root = data_root(args.target)
    proj = repo / "projects" / PROJECT_ID
    if not proj.is_dir():
        die(f"仓库里找不到工程目录：{proj}")

    uid = resolve_uid(args.uid, root)
    print(f"工程路径：{proj}")
    print(f"本机账号：{uid}")
    register(root, proj, uid, args.dry_run)
    if not args.dry_run:
        ok("已登记。编辑器打开的是这份 clone 目录 —— 你在这里的改动会直接进 git。")
        warn("别把 .creator/ 和 ai-*-config.json 提交上去（.gitignore 已挡，别手动 --force 绕过）。")
    return 0


def cmd_sync(args) -> int:
    """把仓库里的工程覆盖到已登记的本机路径，保留运行时产物"""
    repo = Path(args.repo).resolve()
    root = data_root(args.target)
    src = repo / "projects" / PROJECT_ID
    if not src.is_dir():
        die(f"仓库里找不到工程目录：{src}")

    target = Path(args.dest).expanduser().resolve() if args.dest else None
    if target is None:
        # 找已登记的记录：路径以 PROJECT_ID 结尾
        for r in load_records(root):
            p = r.get("projectPath", "")
            if normalize(p).endswith(normalize(PROJECT_ID)):
                target = Path(p)
                break
    if target is None:
        die("没找到已登记的本机工程。先跑一次 install，或同步回 clone 目录：sync --dest <工程路径>。")
    if not target.is_dir():
        die(f"目标路径不存在：{target}")

    print(f"仓库工程：{src}")
    print(f"覆盖目标：{target}")
    if normalize(str(target)) == normalize(str(src)):
        info("目标就是仓库本身，无需同步。")
        return 0

    for item in PROJECT_ITEMS:
        s, d = src / item, target / item
        if not s.exists():
            continue
        if args.dry_run:
            info(f"[dry-run] {item} → {d}")
            continue
        if s.is_dir():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            if d.exists():
                shutil.copy2(d, d.with_name(d.name + f".bak-{stamp()}"))
            shutil.copy2(s, d)
        print(f"  ↻ {item}")

    if not args.dry_run:
        ok("同步完成。运行时产物（.creator/、ai-*-config.json）已保留。")
    return 0


# ---------------------------------------------------------------- CLI

def main() -> int:
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(
        prog="world.py",
        description="DY-AI_TOWN 世界工程同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python tools/world.py verify
  python tools/world.py install
  python tools/world.py link
  python tools/world.py sync
  python tools/world.py verify --update-manifest
""")
    ap.add_argument("--repo", default=str(here), help="仓库根目录（默认脚本上级目录）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="校验文件哈希与仓库卫生（只读）")
    v.add_argument("--json", action="store_true", help="输出 JSON，供 CI 使用")
    v.add_argument("--no-hygiene", action="store_true", help="跳过黑名单检查")
    v.add_argument("--update-manifest", action="store_true", help="校验通过后刷新 项目清单.json")
    v.set_defaults(func=cmd_verify)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--target", help="编辑器数据目录（默认自动定位，测试时可指向假目录）")
    shared.add_argument("--uid", help="手动指定账号 uid（默认从编辑器 config.json 读）")
    shared.add_argument("--dry-run", action="store_true", help="只打印将要做什么，不落盘")

    i = sub.add_parser("install", parents=[shared], help="复制进编辑器并登记")
    i.set_defaults(func=cmd_install)

    l = sub.add_parser("link", parents=[shared], help="不复制，直接登记仓库路径")
    l.set_defaults(func=cmd_link)

    s = sub.add_parser("sync", parents=[shared], help="把仓库工程覆盖到已登记路径")
    s.add_argument("--dest", help="手动指定目标工程路径")
    s.set_defaults(func=cmd_sync)

    n = sub.add_parser("normalize", help="按 .gitattributes 统一换行符（Windows 上改完文件跑一次）")
    n.set_defaults(func=cmd_normalize)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
