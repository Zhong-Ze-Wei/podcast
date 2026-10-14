# -*- coding: utf-8 -*-
"""补捞 v3：6 端口并发，每通道独立出口节点，限流只换本通道节点"""
from dotenv import load_dotenv; load_dotenv()
import queue
import threading
import time
from datetime import datetime

from pymongo import MongoClient

from app.services import clash_service
from app.services.youtube_service import YouTubeService
from app.models.transcript import Transcript
from app.models.episode import Episode
from app.config import Config

LANES = [7891, 7892, 7893, 7894, 7895, 7896]
THROTTLE_TOKENS = ("无法连接", "Too Many", "429", "timed out")

db = MongoClient(Config.MONGO_URI)[Config.MONGO_DB]
stuck = list(db.episodes.find({'audio_type': 'video/youtube', 'has_transcript': {'$ne': True}}, {'_id':1,'guid':1,'title':1,'owner_id':1,'status':1}))
print('待补捞:', len(stuck), flush=True)

# 通道初始化：六个通道各占一个不同区域（被烧过的区域换得快，区域分散 = 配额分散）
nodes = clash_service.node_names(f"Port-7891-Node")
by_region = {}
for node in nodes:
    region = node.split(" - ")[0].strip()
    by_region.setdefault(region, node)
preferred = ["DE", "KR", "NL", "TR", "GB", "FR", "CA", "JP", "SG", "TW", "HK", "US"]
picked = [by_region[r] for r in preferred if r in by_region]
spread = (picked + list(dict.fromkeys(nodes)))[:len(LANES)]
for port, node in zip(LANES, spread):
    clash_service.select_node(node, group=f"Port-{port}-Node")
print('通道节点:', {p: clash_service.current_node(f"Port-{p}-Node") for p in LANES}, flush=True)

work = queue.Queue()
for e in stuck:
    work.put(e)
stats = {"ok": 0, "fail": 0}
lock = threading.Lock()

def persist(e, tr):
    if db.transcripts.find_one({'episode_id': e['_id']}):
        return False
    db.transcripts.insert_one(Transcript.create(
        episode_id=e['_id'], owner_id=e.get('owner_id'),
        text=tr['text'], segments=tr['segments'], language=tr.get('language', ''),
        source='youtube', model=''))
    updates = {'has_transcript': True, 'transcript_source': 'youtube',
               'transcript_fetch_error': None, 'updated_at': datetime.utcnow()}
    if e.get('status') not in (Episode.STATUS_SUMMARIZED, Episode.STATUS_SUMMARIZING):
        updates['status'] = Episode.STATUS_TRANSCRIBED
    db.episodes.update_one({'_id': e['_id']}, {'$set': updates})
    return True

def worker(port):
    proxy = f"http://127.0.0.1:{port}"
    group = f"Port-{port}-Node"
    while True:
        try:
            e = work.get_nowait()
        except queue.Empty:
            return
        vid = e['guid'].replace('youtube:', '')
        tr, err = YouTubeService.fetch_transcript(vid, proxy=proxy)
        if tr is None and err and any(t in str(err) for t in THROTTLE_TOKENS):
            switched = clash_service.rotate_next(group)  # 只换本通道节点
            if switched:
                tr, err = YouTubeService.fetch_transcript(vid, proxy=proxy)
        if tr and persist(e, tr):
            with lock:
                stats["ok"] += 1
            print(f"OK{port} [{clash_service.current_node(group)[:12]}] {e['title'][:36]}", flush=True)
        else:
            db.episodes.update_one({'_id': e['_id']}, {'$set': {'transcript_fetch_error': str(err or '未知')[:120]}})
            with lock:
                stats["fail"] += 1
            print(f"FAIL{port} {e['title'][:30]} | {str(err)[:36]}", flush=True)
        time.sleep(3)

threads = [threading.Thread(target=worker, args=(p,)) for p in LANES]
for t in threads: t.start()
for t in threads: t.join()
print(f"完成: 成功 {stats['ok']} / 失败 {stats['fail']}", flush=True)
