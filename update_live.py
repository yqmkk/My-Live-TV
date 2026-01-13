import requests
import re
import concurrent.futures
import time

# --- 配置区 ---
# 增加了更多高质量源仓库
SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/joevess/IPTV/main/sources/iptv_sources.m3u"
]

EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
LOGO_BASE = "https://live.fanmingming.com/tv/"
TIMEOUT = 2  # 超过2秒的源不要，保证流畅度
MAX_WORKERS = 80 

def clean_channel_name(name):
    """标准化频道名，这是关联单独节目单的关键"""
    name = name.upper()
    name = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|高清|标清|HD|SD|频道|字幕|IPV6|IPV4|-', '', name)
    name = name.replace(' ', '')
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

def check_url(channel):
    name, url = channel
    std_name = clean_channel_name(name)
    try:
        start_time = time.time()
        # 模拟真实播放器 User-Agent
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        response = requests.get(url, timeout=TIMEOUT, stream=True, headers=headers)
        if response.status_code == 200:
            if time.time() - start_time < TIMEOUT:
                group = "央视频道" if "CCTV" in std_name else ("卫视频道" if "卫视" in std_name else "地方/其他")
                logo = f"{LOGO_BASE}{std_name}.png"
                return {"name": std_name, "url": url, "group": group, "logo": logo}
    except:
        pass
    return None

def main():
    tasks = []
    seen_urls = set()
    print("正在搜刮全网优质直播源...")
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

    print(f"原始链接: {len(tasks)}，正在筛选流畅源...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    results.sort(key=lambda x: (x['group'], x['name']))

    # 1. 生成 M3U 文件
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://cdn.jsdelivr.net/gh/yqmkk/My-Live-TV@main/epg.xml"\n')
        for item in results:
            # tvg-name 必须和 epg.xml 里的频道 ID 匹配
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 2. 同步并生成专属节目单文件
    print("正在同步单独订阅的节目单地址...")
    try:
        epg_resp = requests.get(EPG_SOURCE, timeout=30)
        with open("epg.xml", "wb") as f:
            f.write(epg_resp.content)
        print("节目单 epg.xml 已就绪")
    except:
        print("节目单同步失败")

if __name__ == "__main__":
    main()
