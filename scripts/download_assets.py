#!/usr/bin/env python3
"""
一键下载安装与初始化资源脚本:
1. 下载并安装对应操作系统与架构的官方最新/稳定 Stockfish 引擎可执行文件
2. 检查并自动安装来自 lichess-org/chess-openings 的开局库 (openings.json)
"""
import os
import sys
import platform
import shutil
import zipfile
import tarfile
import json
import io
import urllib.request
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
ENGINES_DIR = BASE_DIR / "engines"
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"

USER_AGENT = "Mozilla/5.0 (compatible; ChessMaidBot-Installer/1.0)"


def download_stream(url: str, dest_path: Path) -> bool:
    """流式下载大文件并保存到指定路径"""
    print(f"[下载] 开始从 {url} 下载...")
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
            shutil.copyfileobj(resp, out)
        print(f"[下载完成] {dest_path.name} ({dest_path.stat().st_size / (1024 * 1024):.2f} MB)")
        return True
    except Exception as e:
        print(f"[下载失败] {url} -> {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def get_candidate_urls(system: str, machine: str) -> List[str]:
    """根据操作系统与 CPU 架构提供官方 Release 下载候选列表"""
    base_sf18 = "https://github.com/official-stockfish/Stockfish/releases/download/sf_18"
    machine = machine.lower()
    urls = []

    if system == "Linux":
        if "arm" in machine or "aarch64" in machine:
            urls = [
                f"{base_sf18}/stockfish-android-armv8-dotprod.tar",
                f"{base_sf18}/stockfish-android-armv8.tar",
            ]
        else:
            urls = [
                f"{base_sf18}/stockfish-ubuntu-x86-64-avx2.tar",
                f"{base_sf18}/stockfish-ubuntu-x86-64-sse41-popcnt.tar",
                f"{base_sf18}/stockfish-ubuntu-x86-64.tar",
            ]
    elif system == "Darwin":
        if "arm" in machine or "aarch64" in machine:
            urls = [
                f"{base_sf18}/stockfish-macos-m1-apple-silicon.tar",
                f"{base_sf18}/stockfish-macos-x86-64-avx2.tar",
            ]
        else:
            urls = [
                f"{base_sf18}/stockfish-macos-x86-64-avx2.tar",
                f"{base_sf18}/stockfish-macos-x86-64-sse41-popcnt.tar",
                f"{base_sf18}/stockfish-macos-x86-64.tar",
            ]
    elif system == "Windows":
        if "arm" in machine or "aarch64" in machine:
            urls = [
                f"{base_sf18}/stockfish-windows-armv8-dotprod.zip",
                f"{base_sf18}/stockfish-windows-armv8.zip",
            ]
        else:
            urls = [
                f"{base_sf18}/stockfish-windows-x86-64-avx2.zip",
                f"{base_sf18}/stockfish-windows-x86-64-sse41-popcnt.zip",
                f"{base_sf18}/stockfish-windows-x86-64.zip",
            ]
    return urls


def is_valid_stockfish_binary(path: Path) -> bool:
    """验证二进制文件是否存在、是否为真实 ELF/PE/Mach-O 且大小正常"""
    if not path.exists() or not path.is_file():
        return False
    # Stockfish 官方带有神经网络权重，通常大于 20MB
    if path.stat().st_size < 1000000:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
            # Linux ELF: \x7fELF, Windows PE: MZ, macOS Mach-O: \xcf\xfa\xed\xfe / \xfe\xed\xfa\xcf / \xca\xfe\xba\xbe
            if header.startswith(b"\x7fELF") or header.startswith(b"MZ") or header in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xce\xfa\xed\xfe"):
                return True
            # 通用回退：若大于 5MB 也大概率是编译后的二进制而非 markdown 文档
            return path.stat().st_size > 5000000
    except Exception:
        return False


def extract_stockfish_from_archive(archive_path: Path, target_path: Path, system: str) -> bool:
    """从 tar 或 zip 压缩包中精准提取真实 Stockfish 引擎可执行文件"""
    print(f"[解压] 正在从 {archive_path.name} 提取引擎可执行程序...")
    temp_target = target_path.with_suffix(".tmp")
    extracted = False

    try:
        if archive_path.suffix == ".zip" or zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as z:
                best_member = None
                max_size = 0
                for info in z.infolist():
                    name_lower = info.filename.lower()
                    if name_lower.endswith((".md", ".txt", ".sh", ".h", ".cpp", ".cff")):
                        continue
                    if "stockfish" in name_lower and info.file_size > max_size:
                        max_size = info.file_size
                        best_member = info

                if best_member:
                    with z.open(best_member) as src, open(temp_target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted = True
        else:
            with tarfile.open(archive_path, 'r:*') as tar:
                best_member = None
                max_size = 0
                for member in tar.getmembers():
                    if not member.isfile():
                        continue
                    name_lower = member.name.lower()
                    if name_lower.endswith((".md", ".txt", ".sh", ".h", ".cpp", ".cff", ".json")):
                        continue
                    if "stockfish" in name_lower and member.size > max_size:
                        max_size = member.size
                        best_member = member

                if best_member:
                    src = tar.extractfile(best_member)
                    if src:
                        with open(temp_target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        extracted = True

        if extracted and is_valid_stockfish_binary(temp_target):
            if target_path.exists():
                target_path.unlink()
            temp_target.rename(target_path)
            if system != "Windows":
                os.chmod(target_path, 0o755)
            print(f"[提取成功] 引擎文件已写入: {target_path}")
            return True
        else:
            print("[提取失败] 未能在压缩包中找到合法的 Stockfish 二进制")
            if temp_target.exists():
                temp_target.unlink()
            return False
    except Exception as e:
        print(f"[解压异常] {e}")
        if temp_target.exists():
            temp_target.unlink()
        return False


def setup_stockfish() -> bool:
    """检测并自动下载配置 Stockfish 引擎"""
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)
    current_os = platform.system()
    machine = platform.machine()
    dest_binary = ENGINES_DIR / ("stockfish.exe" if current_os == "Windows" else "stockfish")

    # 1. 如果已存在合法的二进制可执行文件，则跳过下载
    if is_valid_stockfish_binary(dest_binary):
        if current_os != "Windows":
            os.chmod(dest_binary, 0o755)
        print(f"[OK] Stockfish 引擎已就绪: {dest_binary}")
        return True

    # 2. 如果存在错误下载的文档（比如小于 1MB 或文本文件），先清理
    if dest_binary.exists():
        print("[清理] 检测到残存的无效 Stockfish 文件，正在移除...")
        dest_binary.unlink()

    # 3. 尝试候选下载链接
    candidate_urls = get_candidate_urls(current_os, machine)
    if not candidate_urls:
        print(f"[WARN] 未找到适用于操作系统 {current_os} ({machine}) 的预设下载链接")
        return False

    archive_ext = ".zip" if current_os == "Windows" else ".tar"
    archive_path = ENGINES_DIR / f"stockfish_dl{archive_ext}"

    for url in candidate_urls:
        if download_stream(url, archive_path):
            success = extract_stockfish_from_archive(archive_path, dest_binary, current_os)
            if archive_path.exists():
                archive_path.unlink()
            if success:
                return True

    print("[WARN] 无法完成 Stockfish 自动下载与提取，请手动将引擎二进制放置于 engines/stockfish")
    return False


def setup_openings_database() -> bool:
    """检查并自动从 https://github.com/lichess-org/chess-openings 下载与构建开局库"""
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    openings_file = BOOKS_DIR / "openings.json"

    # 如果已有大于 50KB 的开局库文件，则视为完备
    if openings_file.exists() and openings_file.stat().st_size > 50000:
        print(f"[OK] Lichess 开局库已就绪: {openings_file} ({openings_file.stat().st_size / 1024:.1f} KB)")
        return True

    print("[下载] 正在从 https://github.com/lichess-org/chess-openings 下载并构建开局库...")
    fast_templates = [
        "https://fastly.jsdelivr.net/gh/lichess-org/chess-openings@master/{}.tsv",
        "https://cdn.jsdelivr.net/gh/lichess-org/chess-openings@master/{}.tsv",
        "https://raw.githubusercontent.com/lichess-org/chess-openings/master/{}.tsv",
    ]

    import chess
    import chess.pgn
    from src.database.opening_book import DEFAULT_OPENING_PATTERNS

    openings_db = dict(DEFAULT_OPENING_PATTERNS)

    for letter in ['a', 'b', 'c', 'd', 'e']:
        content = None
        for template in fast_templates:
            url = template.format(letter)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    content = resp.read().decode("utf-8")
                    break
            except Exception:
                continue

        if not content:
            print(f"[WARN] 无法获取开局库分卷 {letter}.tsv，使用默认开局库兜底")
            continue

        lines = content.splitlines()
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) >= 3:
                eco, name, pgn = parts[0], parts[1], parts[2]
                try:
                    game = chess.pgn.read_game(io.StringIO(pgn))
                    if game:
                        b = game.board()
                        for m in game.mainline_moves():
                            b.push(m)
                        fen_core = " ".join(b.fen().split()[:4])
                        # 存入开局映射
                        if fen_core not in openings_db:
                            openings_db[fen_core] = {
                                "eco": eco,
                                "name": name,
                                "moves": []
                            }
                        else:
                            openings_db[fen_core]["eco"] = eco
                            openings_db[fen_core]["name"] = name
                except Exception:
                    pass

    try:
        with open(openings_file, "w", encoding="utf-8") as f:
            json.dump(openings_db, f, ensure_ascii=False, indent=2)
        print(f"[OK] Lichess 开局库已成功安装并索引 ({len(openings_db)} 个局面): {openings_file}")
        return True
    except Exception as e:
        print(f"[WARN] 保存开局库失败: {e}")
        return False


def setup_databases() -> bool:
    """初始化并补齐开局库"""
    return setup_openings_database()


def main():
    print("=== ChessMaidBot 依赖资源与引擎一键配置工具 ===")
    setup_openings_database()
    setup_stockfish()
    print("=== 准备完毕，可以直接启动应用！ ===")


if __name__ == "__main__":
    main()
