# -*- coding: utf-8 -*-
"""把数据库里的 Windows 绝对媒体路径改写成 MEDIA_ROOT 相对路径。

历史原因，7 个节目的 local_path 存成了绝对路径
（E:\\...\\backend\\media\\audio\\yt_xxx.webm），换机器即失效。
audio_storage.py / episodes.py 消费 local_path 时本来就优先支持
MEDIA_ROOT 相对路径，因此改写成相对形式是一劳永逸的：
任何系统、任何盘符、任何克隆位置都能用。

用法（在 backend 容器内，或任何有 pymongo 的环境）：
    python rewrite_windows_paths.py           # 只打印将要做的改动
    python rewrite_windows_paths.py --apply   # 实际写回数据库

环境变量：MONGO_URI / MONGO_DB / MEDIA_ROOT，缺省用 app 配置。
"""
import os
import re
import sys

DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
MEDIA_BOUNDARY = re.compile(r"[\\/]media[\\/]")


def to_relative(absolute_path):
    """E:\\...\\media\\audio\\x.webm -> audio/x.webm；不含 media 边界返回 None。"""
    parts = MEDIA_BOUNDARY.split(absolute_path.replace("\\", "/"))
    return parts[-1].strip("/") if len(parts) >= 2 else None


def main(apply):
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "podcast")
    media_root = os.getenv("MEDIA_ROOT") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media"
    )
    db = MongoClient(uri)[db_name]

    fields = ("local_path", "audio_path")
    query = {"$or": [{field: DRIVE_PATH} for field in fields]}
    episodes = list(db.episodes.find(query, {"local_path": 1, "audio_path": 1, "title": 1}))
    print(f"发现 {len(episodes)} 条含绝对路径的记录（MEDIA_ROOT={media_root}）")

    changed, missing = 0, []
    for episode in episodes:
        updates = {}
        for field in fields:
            value = episode.get(field)
            if not value or not DRIVE_PATH.match(value):
                continue
            relative = to_relative(value)
            if not relative:
                print(f"  跳过（不含 media 边界）: {episode['_id']} {value}")
                continue
            if not os.path.isfile(os.path.join(media_root, relative)):
                missing.append(relative)
                print(f"  警告: 文件不存在 {relative}")
                continue
            updates[field] = relative
        if not updates:
            continue
        changed += 1
        detail = ", ".join(f"{k}: {episode.get(k, '')!r} -> {updates[k]!r}" for k in updates)
        print(f"  {episode.get('title', '')[:40]} | {detail}")
        if apply:
            db.episodes.update_one({"_id": episode["_id"]}, {"$set": updates})

    if missing:
        print(f"\n有 {len(missing)} 个文件在 MEDIA_ROOT 下找不到，未改写：")
        for item in missing:
            print(f"  {item}")
    print(f"\n{'已改写' if apply else '将改写'} {changed} 条记录"
          + ("" if apply else "（加 --apply 实际执行）"))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
