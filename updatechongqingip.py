import requests
import re
import time
import cv2

# FOFA 查询地址
fofa_url = 'https://fofa.info/result?qbase64=c2VydmVyPSJ1ZHB4eSIgJiYgY2l0eT0iQ2hvbmdxaW5nIiAmJiBvcmchPSJDaGluYW5ldCIgJiYgb3JnIT0iQ2hpbmEgVGVsZWNvbSI=&filter_type=last_month'
# fofa_url = 'https://fofa.info/result?qbase64=InVkcHh5IiAmJiBjaXR5PSJDaG9uZ3Fpbmci'

# 组播地址
urls_udp = "/udp/225.0.4.188:7980"

# 提取IP:PORT
def extract_unique_ip_ports(fofa_url):
    try:
        response = requests.get(fofa_url, timeout=10)
        ips_ports = re.findall(r'(\d+\.\d+\.\d+\.\d+:\d+)', response.text)
        return list(set(ips_ports))
    except requests.RequestException as e:
        print(f"请求错误: {e}")
        return []


# 基础连通性检测
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


# 视频流测速函数
def measure_stream_speed(ip_port, test_duration=8):
    video_url = f"http://{ip_port}{urls_udp}"
    print(f"测速中: {video_url}")

    try:
        start_time = time.time()
        bytes_received = 0

        with requests.get(video_url, stream=True, timeout=10) as r:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    bytes_received += len(chunk)

                if time.time() - start_time > test_duration:
                    break

        elapsed = time.time() - start_time
        mbps = (bytes_received * 8) / elapsed / 1024 / 1024
        print(f"{ip_port} 速度: {mbps:.2f} Mbps")

        return mbps

    except Exception as e:
        print(f"{ip_port} 测速失败: {e}")
        return 0


# 更新文件
def update_files(best_ip_port, files_to_update):
    for file_info in files_to_update:
        try:
            response = requests.get(file_info['url'], timeout=10)
            file_content = response.text

            ip_port_pattern = r'(http://\d+\.\d+\.\d+\.\d+:\d+)'
            updated_content = re.sub(
                ip_port_pattern,
                f'http://{best_ip_port}',
                file_content
            )

            with open(file_info['filename'], 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"{file_info['filename']} 更新完成")

        except Exception as e:
            print(f"更新失败: {e}")


# 主程序
unique_ips_ports = extract_unique_ip_ports(fofa_url)

if not unique_ips_ports:
    print("未找到IP")
    exit()

print(f"共提取 {len(unique_ips_ports)} 个IP")

# Step 1: 找到5个可用代理
valid_servers = []

for ip_port in unique_ips_ports:
    print(f"检测: {ip_port}")
    if check_video_stream_connectivity(ip_port):
        print(f"可用: {ip_port}")
        valid_servers.append(ip_port)

        if len(valid_servers) >= 5:
            break

if len(valid_servers) < 5:
    print("可用代理不足5个")
    exit()

print("\n开始测速...")

# Step 2: 测速
speed_results = {}

for server in valid_servers:
    speed = measure_stream_speed(server)
    speed_results[server] = speed

# Step 3: 选择最快的
best_server = max(speed_results, key=speed_results.get)

print("\n测速结果:")
for server, speed in speed_results.items():
    print(f"{server} -> {speed:.2f} Mbps")

print(f"\n最快服务器: {best_server}")

# Step 4: 更新文件
files_to_update = [
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.txt', 'filename': 'CQTV.txt'},
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.m3u', 'filename': 'CQTV.m3u'}
]

update_files(best_server, files_to_update)


