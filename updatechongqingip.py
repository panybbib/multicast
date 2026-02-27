import requests
import re
import time
import cv2
import json
import os

fofa_url = 'https://fofa.info/result?qbase64=c2VydmVyPSJ1ZHB4eSIgJiYgY2l0eT0iQ2hvbmdxaW5nIiAmJiBvcmchPSJDaGluYW5ldCIgJiYgb3JnIT0iQ2hpbmEgVGVsZWNvbSI=&filter_type=last_month'
urls_udp = "/udp/225.0.4.188:7980"

BACKUP_FILE = "backup.json"

# ---------------- 基础函数 ----------------

def extract_unique_ip_ports(url):
    try:
        r = requests.get(url, timeout=10)
        ips_ports = re.findall(r'(\d+\.\d+\.\d+\.\d+:\d+)', r.text)
        return list(set(ips_ports))
    except:
        return []

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
    """
    返回：
    {
        throughput_mbps,
        ttfb_ms,
        loss_ratio
    }
    """
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

                if last_chunk_time is not None:
                    if now - last_chunk_time > stall_threshold:
                        stall_count += 1

                last_chunk_time = now

                if chunk:
                    bytes_received += len(chunk)
                    chunk_count += 1

                if now - start_req > test_duration:
                    break

        elapsed = time.time() - start_req
        throughput = (bytes_received * 8) / elapsed / 1024 / 1024

        if chunk_count == 0:
            loss_ratio = 1
        else:
            loss_ratio = stall_count / chunk_count

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

    min_t = min(throughputs)
    max_t = max(throughputs)

    min_l = min(ttfbs)
    max_l = max(ttfbs)

    scores = {}

    for ip, r in results.items():
        # 归一化
        if max_t != min_t:
            norm_tp = (r["throughput"] - min_t) / (max_t - min_t)
        else:
            norm_tp = 1

        if max_l != min_l:
            norm_latency = (r["ttfb"] - min_l) / (max_l - min_l)
        else:
            norm_latency = 0

        score = (
            0.7 * norm_tp +
            0.2 * (1 - norm_latency) +
            0.1 * (1 - r["loss"])
        )

        scores[ip] = score

    return scores

# ---------------- 备份机制 ----------------

def load_backup():
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "r") as f:
            return json.load(f)
    return None

def save_backup(primary, secondary):
    with open(BACKUP_FILE, "w") as f:
        json.dump({
            "primary": primary,
            "secondary": secondary
        }, f)

# ---------------- 文件更新 ----------------

def update_files(target_ip_port, files):
    for file_info in files:
        try:
            r = requests.get(file_info['url'], timeout=10)
            content = re.sub(
                r'(http://\d+\.\d+\.\d+\.\d+:\d+)',
                f'http://{target_ip_port}',
                r.text
            )
            with open(file_info['filename'], 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"{file_info['filename']} 更新 -> {target_ip_port}")
        except Exception as e:
            print(f"更新失败: {e}")

# ---------------- 主程序 ----------------

ips = extract_unique_ip_ports(fofa_url)
valid_servers = []

for ip in ips:
    if check_video_stream_connectivity(ip):
        valid_servers.append(ip)
    if len(valid_servers) >= 6:
        break

# if len(valid_servers) < 2:
#    print("可用节点不足")
#    exit()

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

# 保存备份
save_backup(primary, secondary)

# 更新文件
files_group_1 = [
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.txt', 'filename': 'CQTV.txt'},
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.m3u', 'filename': 'CQTV.m3u'}
]

files_group_2 = [
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.txt', 'filename': 'CQTV2.txt'},
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.m3u', 'filename': 'CQTV2.m3u'}
]

update_files(primary, files_group_1)
update_files(secondary, files_group_2)

print("\n完成")
