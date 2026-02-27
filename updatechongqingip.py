import requests
import re
import time
import cv2
import json
import os
import base64

# 参数
FMB = "cGFuLjEwN0AxNjMuY29t"
FKB = "NjgyODE2NmEzZjRmYjdlYTQ2ZDkyOTQ0NjdmNDQ1YmU="
FQUERY = 'server="udpXy" && city="Chongqing" && org!="Chinanet" && org!="China Telecom"'

# UDP路径
urls_udp = "/udp/225.0.4.188:7980"

BACKUP_FILE = "backup.json"

# ---------------- 查询 ----------------

def fetch_fofa_results(query, size=100):
    FMA = base64.b64decode(FMB).decode()
    FKA = base64.b64decode(FKB).decode()
    qbase64 = base64.b64encode(query.encode()).decode()
    
    url = "https://fofa.info/api/v1/search/all"

    params = {
        "email": FMA,
        "key": FKA,
        "qbase64": qbase64,
        "fields": "ip,port",
        "size": size
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if data.get("error"):
            print("FOFA错误:", data["error"])
            return []

        if not data.get("results"):
            print("无结果或额度不足")
            return []

        ip_ports = []
        for item in data["results"]:
            ip = item[0]
            port = item[1]
            ip_ports.append(f"{ip}:{port}")

        return list(set(ip_ports))

    except Exception as e:
        print("FOFA 查询失败:", e)
        return []

# ---------------- 视频连通性检测 ----------------

def check_video_stream_connectivity(ip_port):
    try:
        video_url = f"http://{ip_port}{urls_udp}"
        cap = cv2.VideoCapture(video_url)
        if not cap.isOpened():
            return False
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return width > 0 and height > 0
    except:
        return False

# ---------------- 综合测速 ----------------

def measure_stream_quality(ip_port, test_duration=5, stall_threshold=0.8):
    video_url = f"http://{ip_port}{urls_udp}"
    print(f"\n测试: {ip_port}")

    try:
        start_req = time.time()
        bytes_received = 0
        stall_count = 0
        chunk_count = 0
        first_byte_time = None
        last_chunk_time = None

        with requests.get(video_url, stream=True, timeout=10) as r:
            for chunk in r.iter_content(chunk_size=8192):
                now = time.time()

                if first_byte_time is None:
                    first_byte_time = now
                    ttfb_ms = (first_byte_time - start_req) * 1000

                if last_chunk_time and now - last_chunk_time > stall_threshold:
                    stall_count += 1

                last_chunk_time = now

                if chunk:
                    bytes_received += len(chunk)
                    chunk_count += 1

                if now - start_req > test_duration:
                    break

        elapsed = time.time() - start_req
        throughput = (bytes_received * 8) / elapsed / 1024 / 1024

        loss_ratio = stall_count / chunk_count if chunk_count else 1

        print(f"带宽: {throughput:.2f} Mbps | TTFB: {ttfb_ms:.0f} ms | 丢包率估算: {loss_ratio:.2%}")

        return {
            "throughput": throughput,
            "ttfb": ttfb_ms,
            "loss": loss_ratio
        }

    except Exception as e:
        print(f"失败: {e}")
        return None

# ---------------- 评分 ----------------

def compute_scores(results):
    throughputs = [r["throughput"] for r in results.values()]
    ttfbs = [r["ttfb"] for r in results.values()]

    min_t, max_t = min(throughputs), max(throughputs)
    min_l, max_l = min(ttfbs), max(ttfbs)

    scores = {}

    for ip, r in results.items():
        norm_tp = (r["throughput"] - min_t) / (max_t - min_t) if max_t != min_t else 1
        norm_latency = (r["ttfb"] - min_l) / (max_l - min_l) if max_l != min_l else 0

        score = 0.7 * norm_tp + 0.2 * (1 - norm_latency) + 0.1 * (1 - r["loss"])
        scores[ip] = score

    return scores

# ---------------- 主程序 ----------------

print("正在查询 FOFA...")
ips = fetch_fofa_results(FQUERY, size=100)

if not ips:
    print("未获取到IP")
    exit()

valid_servers = []

for ip in ips:
    if check_video_stream_connectivity(ip):
        valid_servers.append(ip)
    if len(valid_servers) >= 9:
        break

results = {}

for ip in valid_servers:
    data = measure_stream_quality(ip)
    if data:
        results[ip] = data

if len(results) < 2:
    print("测速有效节点不足")
    exit()

scores = compute_scores(results)
sorted_servers = sorted(scores.items(), key=lambda x: x[1], reverse=True)

primary = sorted_servers[0][0]
secondary = sorted_servers[1][0]

print("\n综合评分排名:")
for ip, score in sorted_servers:
    print(f"{ip} -> {score:.3f}")

print(f"\n主节点: {primary}")
print(f"备用节点: {secondary}")

print("\n完成")
