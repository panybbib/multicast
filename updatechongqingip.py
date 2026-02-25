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


# 视频流测速
def measure_stream_speed(ip_port, test_duration=5):
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


# 更新文件函数（指定目标IP）
def update_files(target_ip_port, files_to_update):
    for file_info in files_to_update:
        try:
            response = requests.get(file_info['url'], timeout=10)
            file_content = response.text

            ip_port_pattern = r'(http://\d+\.\d+\.\d+\.\d+:\d+)'
            updated_content = re.sub(
                ip_port_pattern,
                f'http://{target_ip_port}',
                file_content
            )

            with open(file_info['filename'], 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"{file_info['filename']} 更新完成 -> {target_ip_port}")

        except Exception as e:
            print(f"{file_info['filename']} 更新失败: {e}")


# 主程序
unique_ips_ports = extract_unique_ip_ports(fofa_url)

if not unique_ips_ports:
    print("未找到IP")
    exit()

print(f"共提取 {len(unique_ips_ports)} 个IP")

# Step 1: 找到6个可用代理
valid_servers = []

for ip_port in unique_ips_ports:
    print(f"检测: {ip_port}")
    if check_video_stream_connectivity(ip_port):
        print(f"可用: {ip_port}")
        valid_servers.append(ip_port)

        if len(valid_servers) >= 6:
            break

if len(valid_servers) < 2:
    print("可用代理不足2个")
    exit()

print("\n开始测速...")

# Step 2: 测速
speed_results = {}

for server in valid_servers:
    speed = measure_stream_speed(server)
    if speed > 0:
        speed_results[server] = speed

if len(speed_results) < 2:
    print("测速成功的代理不足2个")
    exit()

# Step 3: 按速度排序，取前2
sorted_servers = sorted(
    speed_results.items(),
    key=lambda x: x[1],
    reverse=True
)

best_server_1 = sorted_servers[0][0]
best_server_2 = sorted_servers[1][0]

print("\n测速排名:")
for server, speed in sorted_servers:
    print(f"{server} -> {speed:.2f} Mbps")

print(f"\n第一快: {best_server_1}")
print(f"第二快: {best_server_2}")

# Step 4: 更新文件

# 第一组文件
files_group_1 = [
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.txt', 'filename': 'CQTV.txt'},
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.m3u', 'filename': 'CQTV.m3u'}
]

# 第二组文件
files_group_2 = [
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.txt', 'filename': 'CQTV2.txt'},
    {'url': 'https://gitjs.tianshideyou.eu.org/https://raw.githubusercontent.com/panybbib/multicast/main/chongqing/CQTV.m3u', 'filename': 'CQTV2.m3u'}
]

update_files(best_server_1, files_group_1)
update_files(best_server_2, files_group_2)

print("\n更新完成")
