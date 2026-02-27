import requests
import re
import time
import cv2
import json
import os
import base64

FMB = "cGFuLjEwN0AxNjMuY29t"
FKB = "NjgyODE2NmEzZjRmYjdlYTQ2ZDkyOTQ0NjdmNDQ1YmU="
FQUERY = 'server="udpXy" && city="Chongqing" && org!="Chinanet" && org!="China Telecom"'
urls_udp = "/udp/225.0.4.188:7980"

# ================= FOFA 查询 =================

def fetch_fofa_results(query, size=100):
    try:
        email = base64.b64decode(FMB).decode()
        key = base64.b64decode(FKB).decode()
    except Exception as e:
        print("凭证失败:", e)
        return []

    qbase64 = base64.b64encode(query.encode()).decode()
    url = "https://fofa.info/api/v1/search/all"

    params = {
        "email": email,
        "key": key,
        "qbase64": qbase64,
        "fields": "ip,port",
        "size": size
    }

    try:
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            print("HTTP错误:", r.status_code)
            print(r.text[:200])
            return []

        try:
            data = r.json()
        except Exception:
            print("返回内容不是JSON:", r.text[:200])
            return []

        if data.get("error"):
            print("FOFA错误:", data.get("errmsg", data.get("error")))
            return []

        results = data.get("results")
        if not results:
            print("无结果或额度不足")
            return []

        ip_ports = []
        for item in results:
            if len(item) >= 2:
                ip_ports.append(f"{item[0]}:{item[1]}")

        print(f"获取到 {len(ip_ports)} 条结果")
        return list(set(ip_ports))

    except requests.RequestException as e:
        print("请求异常:", e)
        return []
    except Exception as e:
        print("未知错误:", e)
        return []

# ================= 视频连通性检测 =================

def check_video_stream_connectivity(ip_port):
    try:
        video_url = f"http://{ip_port}{urls_udp}"
        cap = cv2.VideoCapture(video_url)

        if not cap.isOpened():
            return False

        ret, frame = cap.read()
        cap.release()

        return ret and frame is not None

    except Exception:
        return False

# ================= 综合测速 =================

def measure_stream_quality(ip_port, test_duration=5, stall_threshold=0.8):
    video_url = f"http://{ip_port}{urls_udp}"
    print(f"\n测试: {ip_port}")

    ttfb_ms = 0

    try:
        start_req = time.time()
        bytes_received = 0
        stall_count = 0
        chunk_count = 0
        first_byte_time = None
        last_chunk_time = None

        with requests.get(video_url, stream=True, timeout=10) as r:

            if r.status_code != 200:
                print("HTTP异常:", r.status_code)
                return None

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

        if elapsed <= 0:
            return None

        throughput = (bytes_received * 8) / elapsed / 1024 / 1024
        loss_ratio = stall_count / chunk_count if chunk_count else 1

        print(f"带宽: {throughput:.2f} Mbps | TTFB: {ttfb_ms:.0f} ms | 丢包率估算: {loss_ratio:.2%}")

        return {
            "throughput": throughput,
            "ttfb": ttfb_ms,
            "loss": loss_ratio
        }

    except requests.RequestException:
        return None
    except Exception as e:
        print("测速异常:", e)
        return None

# ================= 评分 =================

def compute_scores(results):
    if not results:
        return {}

    throughputs = [r["throughput"] for r in results.values()]
    ttfbs = [r["ttfb"] for r in results.values()]

    if not throughputs or not ttfbs:
        return {}

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

