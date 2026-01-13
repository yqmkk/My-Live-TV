import requests
import re
import concurrent.futures
import time

# --- 配置区 ---
# 集合了全网最稳的几个源，包含 4K、央视、卫视、数字、地方台
SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/billy21/Tvlist-awesome-m3u-m3u8/master/m3u/migu.m3u"
]

EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
LOGO_BASE = "https://live.fanmingming.com/tv/"
TIMEOUT = 2  # 严格限制：2秒内不响应就剔除
MAX_WORKERS = 100 # 提高并发量，加快检测速度

def clean_channel_name(name):
    name = name.upper()
    name = re.sub(r'\[.*?\]|（.*?）|\(.*?\)', '', name)
    name = re.sub(r'高清|标清|HD|SD|频道|字幕|IPV6|IPV4|CCTV-', 'CCTV', name)
    name = name.replace('-', '').replace(' ', '')
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match:
            num = match.group(1)
            if num == "5P": return "CCTV5+"
            name = f"CCTV-{num}"
        elif "NEWS" in name or "新闻" in name: name = "CCTV-13"
        elif "KIDS" in name or "少儿" in name: name = "CCTV-14"
        elif "MUSIC" in name or "音乐" in name: name = "CCTV-15"
    return name.strip()

def get_metadata(name):
    group = "地方/其他"
    if "CCTV" in name: group = "央视频道"
    elif "卫视" in name: group = "卫视频道"
    elif any(x in name for x in ["4K", "8K"]): group = "超高清"
    logo = f"{LOGO_BASE}{name}.png"
    return group, logo

def check_url(channel):
    name, url = channel
    std_name = clean_channel_name(name)
    group, logo = get_metadata(std_name)
    try:
        start_time = time.time()
        # 增加 headers 模拟播放器，防止被屏蔽
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=TIMEOUT, stream=True, headers=headers)
        if response.status_code == 200:
            # 只取响应极快的
            if time.time() - start_time < TIMEOUT:
                return {"name": std_name, "url": url, "group": group, "logo": logo}
    except:
        pass
    return None

def fetch_build_and_epg():
    tasks = []
    seen_urls = set()
    print("正在聚合全网高清源...")
    for source in SOURCES:
        try:
            r = requests.get(source, timeout=10)
            r.encoding = 'utf-8'
            temp_name = ""
            for line in r.text.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r',(.+)$', line)
                    temp_name = match.group(1) if match else ""
                elif line.startswith("http") and temp_name:
                    if line not in seen_urls:
                        tasks.append((temp_name, line))
                        seen_urls.add(line)
        except: continue

    print(f"原始链接总数: {len(tasks)}，正在进行极速过滤...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            if f.result(): results.append(f.result())

    # 排序
    results.sort(key=lambda x: (x['group'], x['name']))

    # 写入 M3U (引用本地 EPG)
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://raw.githubusercontent.com/yqmkk/My-Live-TV/main/epg.xml"\n')
        for item in results:
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 同步 EPG 节目单到本地
    print("同步节目单数据...")
    try:
        epg_data = requests.get(EPG_SOURCE, timeout=30).content
        with open("epg.xml", "wb") as f:
            f.write(epg_data)
    except:
        print("EPG同步失败，将沿用旧版本")

    print(f"完成！当前有效频道: {len(results)}。")

if __name__ == "__main__":
    fetch_build_and_epg()
