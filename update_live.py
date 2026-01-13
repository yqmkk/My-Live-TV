import requests
import re
import concurrent.futures
import time

# --- 核心配置 ---
SEARCH_KEYWORDS = {
    "🇨🇳中国高清": ["CCTV", "卫视", "数字", "电影", "剧场", "新闻", "体育", "4K", "8K"],
    "🇺🇸美国精选": ["CNN", "HBO", "FOX", "ABC", "NBC", "USA", "DISCOVERY", "MOVIES"],
    "🇯🇵日本精选": ["NHK", "BS", "NTV", "TOKYO", "FUJI", "ASAHI"],
    "🇰🇷韩国精选": ["KBS", "MBC", "SBS", "TVN", "MNET"]
}

RAW_SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/billy21/Tvlist-awesome-m3u-m3u8/master/m3u/migu.m3u",
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u"
]

TIMEOUT = 3
MAX_WORKERS = 100 # 测速较耗资源，适当降低并发确保准确性

def test_speed(url):
    """测试真实下载速度"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        start = time.time()
        # 下载前 1MB 数据来计算速度
        with requests.get(url, timeout=TIMEOUT, stream=True, headers=headers) as r:
            if r.status_code == 200:
                content = b""
                for chunk in r.iter_content(chunk_size=1024*256): # 256KB chunks
                    content += chunk
                    if len(content) >= 1024*1024: # 满 1MB 停止
                        break
                duration = time.time() - start
                speed = len(content) / duration / 1024 / 1024 # MB/s
                return speed
    except:
        pass
    return 0

def check_channel_performance(channel):
    name, url = channel
    name_up = name.upper()
    target_group = next((g for g, keys in SEARCH_KEYWORDS.items() if any(k in name_up for k in keys)), None)
    if not target_group: return None

    speed = test_speed(url)
    # 门槛：下载速度必须大于 1.5MB/s 且小于 100MB/s (防止虚假响应)
    if 1.5 <= speed < 100:
        std_name = name.replace("高清", "").replace("HD", "").replace("-", "").strip()
        return {"name": std_name, "url": url, "group": target_group, "speed": speed}
    return None

def main():
    print("📡 启动急速测速引擎 (过滤卡顿源)...")
    tasks = []
    seen_urls = set()
    for s in RAW_SOURCES:
        try:
            r = requests.get(s, timeout=10)
            name = ""
            for line in r.text.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    name = re.search(r',(.+)$', line).group(1) if "," in line else ""
                elif line.startswith("http") and name:
                    if line not in seen_urls:
                        tasks.append((name, line))
                        seen_urls.add(line)
        except: continue

    print(f"🔍 搜寻到候选 {len(tasks)} 条，开始进行带宽压力测试...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_channel_performance, t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    # 每个频道只保留速度最快的 2 条线路，杜绝播放器反复尝试慢速源
    results.sort(key=lambda x: (x['name'], -x['speed']))
    final_list = []
    counts = {}
    for item in results:
        counts[item['name']] = counts.get(item['name'], 0) + 1
        if counts[item['name']] <= 2: 
            final_list.append(item)

    final_list.sort(key=lambda x: x['group'])

    with open("live_all.m3u", "w", encoding="utf-8") as f:
        # 使用 raw 链接或者更快的加速地址
        f.write(f'#EXTM3U x-tvg-url="https://raw.githubusercontent.com/yqmkk/My-Live-TV/main/epg.xml"\n')
        for item in final_list:
            logo = f"https://live.fanmingming.com/tv/{item['name']}.png"
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{logo}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 缓存 EPG
    try:
        epg = requests.get("http://epg.51zmt.top:8000/e.xml", timeout=60).content
        with open("epg.xml", "wb") as f: f.write(epg)
    except: pass
    print(f"✅ 完成！保留了 {len(final_list)} 个极速频道。")

if __name__ == "__main__":
    main()
