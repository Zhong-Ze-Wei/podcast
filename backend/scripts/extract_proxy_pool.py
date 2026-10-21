#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Clash 订阅配置里提取明协议代理节点，生成 YOUTUBE_PROXY_POOL。

Clash API 出于安全不暴露节点地址；本脚本直接读本机 Verge 的订阅
YAML（仅 socks5/http 节点可直连，vmess/tuic 等加密协议无法绕过
Clash 使用）。逐个探活 YouTube 可达性后输出可直接粘进 .env 的一行。

用法：
    cd backend
    python scripts/extract_proxy_pool.py            # 探活并输出
    python scripts/extract_proxy_pool.py --all      # 不探活，全部输出
"""
import argparse
import glob
import os
import sys
import time

import requests
import yaml

PROFILES = os.path.join(os.environ.get("APPDATA", ""), "io.github.clash-verge-rev.clash-verge-rev", "profiles")
PLAIN_TYPES = ("socks5", "http", "socks", "socks5http")
PROBE_URL = "https://www.youtube.com/robots.txt"


def node_url(node: dict) -> str:
    scheme = "socks5" if "socks" in node.get("type", "").lower() else "http"
    auth = ""
    if node.get("username"):
        auth = f"{node['username']}:{node.get('password', '')}@"
    return f"{scheme}://{auth}{node['server']}:{node['port']}"


def extract(profiles_dir: str):
    found, skipped_tls = {}, 0
    for path in glob.glob(os.path.join(profiles_dir, "*.yaml")):
        try:
            with open(path, encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except Exception:
            continue
        for node in data.get("proxies") or []:
            if not isinstance(node, dict):
                continue
            if str(node.get("type", "")).lower() not in PLAIN_TYPES or not node.get("server") or not node.get("port"):
                continue
            # TLS 包装的 socks5/http 无法用 requests 直连（那是 Clash 类客户端的能力）
            if node.get("tls"):
                skipped_tls += 1
                continue
            url = node_url(node)
            found[node.get("name", url)] = url
    return found, skipped_tls


def probe(url: str, timeout: float = 6.0) -> bool:
    try:
        resp = requests.get(PROBE_URL, proxies={"http": url, "https": url}, timeout=(3, timeout))
        return resp.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="跳过探活，输出全部节点")
    parser.add_argument("--dir", default=PROFILES, help="Verge profiles 目录")
    args = parser.parse_args()

    nodes, skipped_tls = extract(args.dir)
    if skipped_tls:
        print(f"跳过 {skipped_tls} 个 TLS 包装节点（socks5/http over TLS，只能经 Clash 使用，无法直连）")
    if not nodes:
        print(f"未在 {args.dir} 找到可直连的明协议节点（socks5/http 且未开 TLS）")
        return 1
    print(f"共找到 {len(nodes)} 个明协议节点")
    healthy = []
    for name, url in nodes.items():
        if args.all:
            healthy.append((name, url))
            continue
        ok = probe(url)
        print(f"  {'✓' if ok else '✗'} {name}")
        if ok:
            healthy.append((name, url))
        time.sleep(0.2)
    if not healthy:
        print("没有可用节点")
        return 1
    pool = ",".join(url for _name, url in healthy)
    print(f"\n可用 {len(healthy)}/{len(nodes)} 个。把下面这行加入 backend/.env：\n")
    print(f"YOUTUBE_PROXY_POOL={pool}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
