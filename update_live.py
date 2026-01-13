import requests
import re
import concurrent.futures

# --- 配置区 ---
# 集合全网优质源，可以根据需要继续增加
SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u"
]

TIMEOUT = 3  # 测速超时时间（秒）
MAX_WORKERS = 50  # 并行测速线程数

def check_url(channel):
    """检测链接是否可用"""
    name, url, group = channel
    try:
        # 使用 HEAD 请求快速检测
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code == 200:
            return channel
    except:
        try:
            # 部分服务器不支持 HEAD，用 GET 尝试获取前几个字节
            response = requests.get(url, timeout=TIMEOUT, stream=True)
            if response.status_code == 200:
                return channel
        except:
            pass
    return None

def get_group(name):
    """根据频道名自动归类"""
    if "CCTV" in name.upper():
        return "央视频道"
    elif "卫视" in name:
        return "卫视频道"
    elif any(x in name for x in ["4K", "8K", "超高清"]):
        return "超高清频道"
    elif any(x in name for x in ["数字", "电影", "剧场"]):
        return "数字频道"
    else:
        return "地方/其他"

def fetch_and_filter():
    raw_channels = []
    seen_urls = set()

    print("开始抓取全网源...")
    for source_url in SOURCES:
        try:
            res = requests.get(source_url, timeout=10)
            res.encoding = 'utf-8'
            lines = res.text.split('\n')
            
            temp_name = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    # 提取频道名
                    name_match = re.search(r',(.+)$', line)
                    temp_name = name_match.group(1) if name_match else "未知频道"
                elif line.startswith("http") and temp_name:
                    if line not in seen_urls:
                        group = get_group(temp_name)
                        raw_channels.append((temp_name, line, group))
                        seen_urls.add(line)
        except Exception as e:
            print(f"抓取 {source_url} 失败: {e}")

    print(f"抓取完成，共获取 {len(raw_channels)} 条待检测链接。开始并行测速...")

    # 并行测速
    valid_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_url, raw_channels))
        valid_channels = [r for r in results if r is not None]

    # 按分类排序
    valid_channels.sort(key=lambda x: x[2])

    # 写入文件
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U x-tvg-url=\"http://epg.51zmt.top:8000/e.xml\"\n")
        for name, url, group in valid_channels:
            f.write(f'#EXTINF:-1 group-title="{group}",{name}\n')
            f.write(f"{url}\n")
    
    print(f"任务结束：保留有效链接 {len(valid_channels)} 条，已存入 live_all.m3u")

if __name__ == "__main__":
    fetch_and_filter()
