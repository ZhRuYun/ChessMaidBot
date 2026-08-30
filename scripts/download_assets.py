#!/usr/bin/env python3
"""
一键下载安装与初始化脚本:
1. 下载并安装最新 Stockfish 引擎 (针对当前操作系统与架构)
2. 初始化并下载开局库 (Polyglot / openings.json)、EPD 战术题库与 Syzygy 残局库资源
"""
import os
import sys
import platform
import shutil
import zipfile
import tarfile
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
ENGINES_DIR = BASE_DIR / "engines"
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"
TACTICS_DIR = DATA_DIR / "tactics"
SYZYGY_DIR = DATA_DIR / "syzygy"

STOCKFISH_DOWNLOAD_URLS = {
    "Linux": "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar",
    "Darwin": "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-x86-64-avx2.tar",
    "Windows": "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip",
}


def download_file(url: str, dest_path: Path):
    print(f"正在下载: {url} -> {dest_path.name}...")
    headers = {"User-Agent": "ChessMaidBot-Installer"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        shutil.copyfileobj(resp, out)
    print(f"下载完成: {dest_path.name}")


def setup_stockfish():
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)
    current_os = platform.system()
    dest_binary = ENGINES_DIR / ("stockfish.exe" if current_os == "Windows" else "stockfish")
    
    # 检查是否已存在且为有效可执行文件
    if dest_binary.exists() and dest_binary.stat().st_size > 1000000:
        if current_os != "Windows":
            os.chmod(dest_binary, 0o755)
        print(f"[OK] Stockfish 引擎已就绪: {dest_binary}")
        return True

    url = STOCKFISH_DOWNLOAD_URLS.get(current_os)
    if not url:
        print(f"[WARN] 未找到适用于操作系统 {current_os} 的预设 Stockfish 下载链接，请手动下载放置于 engines/stockfish")
        return False

    archive_path = ENGINES_DIR / ("sf_download.zip" if current_os == "Windows" else "sf_download.tar")
    try:
        download_file(url, archive_path)
        if current_os == "Windows":
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    if member.lower().endswith(".exe") and "stockfish" in member.lower():
                        source = zip_ref.open(member)
                        with open(dest_binary, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
        else:
            with tarfile.open(archive_path, 'r') as tar_ref:
                for member in tar_ref.getmembers():
                    if "stockfish" in member.name.lower() and not member.isdir():
                        extracted = tar_ref.extractfile(member)
                        if extracted:
                            with open(dest_binary, "wb") as f:
                                shutil.copyfileobj(extracted, f)
                            break
            if dest_binary.exists():
                os.chmod(dest_binary, 0o755)

        if archive_path.exists():
            archive_path.unlink()

        if dest_binary.exists() and dest_binary.stat().st_size > 100000:
            print(f"[SUCCESS] Stockfish 安装就绪: {dest_binary}")
            return True
        else:
            print(f"[ERROR] Stockfish 提取后文件异常或缺失: {dest_binary}")
            return False
    except Exception as e:
        print(f"[ERROR] 下载或解压 Stockfish 失败: {e}")
        if archive_path.exists():
            archive_path.unlink()
        return False


def setup_databases():
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    TACTICS_DIR.mkdir(parents=True, exist_ok=True)
    SYZYGY_DIR.mkdir(parents=True, exist_ok=True)

    # 导出并完善 openings.json 与 tactics.epd
    from src.database.opening_book import DEFAULT_OPENING_PATTERNS
    from src.database.tactics_db import DEFAULT_EPD_TACTICS
    import json

    openings_file = BOOKS_DIR / "openings.json"
    if not openings_file.exists() or openings_file.stat().st_size < 100:
        with open(openings_file, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_OPENING_PATTERNS, f, ensure_ascii=False, indent=2)
        print(f"[OK] 已生成/更新开局库文件: {openings_file}")
    else:
        print(f"[OK] 开局库文件完备: {openings_file}")

    tactics_file = TACTICS_DIR / "tactics.epd"
    if not tactics_file.exists() or tactics_file.stat().st_size < 50:
        with open(tactics_file, "w", encoding="utf-8") as f:
            for line in DEFAULT_EPD_TACTICS:
                f.write(line + "\n")
        print(f"[OK] 已生成/更新战术题库文件: {tactics_file}")
    else:
        print(f"[OK] 战术题库文件完备: {tactics_file}")

    # Syzygy 残局库说明与目录就绪提示
    readme_syzygy = SYZYGY_DIR / "README.txt"
    if not readme_syzygy.exists():
        with open(readme_syzygy, "w", encoding="utf-8") as f:
            f.write(
                "Syzygy Tablebases 残局库目录\n"
                "如需使用 3-4-5-6 子 Syzygy 残局库，请将 .rtbw 与 .rtbz 文件放入此目录。\n"
                "系统会自动识别并无缝挂载；若无文件则自动启用内置理论残局启发式评估器。\n"
            )
    return True


def main():
    print("=== ChessMaidBot 依赖资源与引擎一键配置工具 ===")
    setup_databases()
    setup_stockfish()
    print("=== 准备完毕，可以直接启动应用！ ===")


if __name__ == "__main__":
    main()
