# -*- coding: utf-8 -*-
"""
Debug summary generation - check what LLM returns
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from bson import ObjectId
from openai import OpenAI

# 获取数据库配置
client = MongoClient('mongodb://localhost:27017')
db = client['podcast']

# 获取 LLM 配置
settings = db.settings.find_one({'key': 'llm_configs'})
config = settings['value'][0]
print(f"LLM Config: {config['base_url']} | {config['model']}")

# 找一个有转录但没有摘要的剧集
episode = db.episodes.find_one({
    'has_transcript': True,
    'has_summary': {'$ne': True}
})

if not episode:
    # 或者找任意一个有转录的
    episode = db.episodes.find_one({'has_transcript': True})

if not episode:
    print("No episode with transcript found")
    exit(1)

print(f"\nEpisode: {episode['title'][:60]}")
print(f"Episode ID: {episode['_id']}")

# 获取转录
transcript = db.transcripts.find_one({'episode_id': episode['_id']})
if not transcript:
    print("No transcript found")
    exit(1)

transcript_text = transcript.get('text', '')
print(f"Transcript length: {len(transcript_text)} chars")

# 读取摘要提示词
from app.services.prompts import PromptRouter
prompt = PromptRouter.get_prompt('investment')
messages = prompt.build_messages(
    transcript=transcript_text[:50000],  # 限制长度
    title=episode.get('title', ''),
    guest=''
)

print(f"\nSystem prompt length: {len(messages[0]['content'])} chars")
print(f"User prompt length: {len(messages[1]['content'])} chars")
print(f"Total prompt length: {sum(len(m['content']) for m in messages)} chars")

# 调用 LLM
llm_client = OpenAI(
    base_url=config['base_url'],
    api_key=config['api_key']
)

print(f"\nCalling LLM ({config['model']})...")
try:
    response = llm_client.chat.completions.create(
        model=config['model'],
        messages=messages,
        max_tokens=4096,
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    print(f"\n=== Response Info ===")
    print(f"Choices count: {len(response.choices)}")

    if response.choices:
        content = response.choices[0].message.content
        print(f"Content type: {type(content)}")
        print(f"Content is None: {content is None}")
        print(f"Content length: {len(content) if content else 0}")

        if content:
            print(f"\n=== Content Preview (first 500 chars) ===")
            print(repr(content[:500]))

            print(f"\n=== Content Preview (last 200 chars) ===")
            print(repr(content[-200:] if len(content) > 200 else content))
        else:
            print("\n[ERROR] Content is empty or None!")

    if response.usage:
        print(f"\n=== Usage ===")
        print(f"Prompt tokens: {response.usage.prompt_tokens}")
        print(f"Completion tokens: {response.usage.completion_tokens}")
        print(f"Total tokens: {response.usage.total_tokens}")

except Exception as e:
    print(f"\n[ERROR] LLM call failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
