import requests
import re
import concurrent.futures
import time

# --- 配置区 ---
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

TIMEOUT = 5  # 增加响应宽限时间
MAX_WORKERS = 50 # 降低并发，防止被源服务器拉黑

def get_performance(url):
    """测试延迟和基本连通性"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        start = time.time()
        # 改为仅请求 Header，确保能连通即可
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers=headers)
        if r.status_code == 200:
            delay = time.time() - start
            return delay
    except:
        pass
    return 999

def check_channel(channel):
    name, url = channel
    name_up = name.upper()
    target_group = next((g for g, keys in SEARCH_KEYWORDS.items() if any(k in name_up for k in keys)), None)
    
    if not target_group: return None

    delay = get_performance(url)
    if delay < TIMEOUT:
        std_name = name.replace("高清", "").replace("HD", "").replace("-", "").strip()
        return {"name": std_name, "url": url, "group": target_group, "delay": delay}
    return None

def main():
    print("🚀 正在重新打捞全网源...")
    tasks = []
    seen_urls = set()
    for s in RAW_SOURCES:
        try:
            r = requests.get(s, timeout=15)
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

    print(f"📡 搜寻到候选 {len(tasks)} 条，正在筛选...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_channel, t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    # 排序：按组排序，同名频道按延迟从小到大排序
    results.sort(key=lambda x: (x['group'], x['name'], x['delay']))
    
    # 每个频道保留前 3 个最快的源
    final_list = []
    counts = {}
    for item in results:
        counts[item['name']] = counts.get(item['name'], 0) + 1
        if counts[item['name']] <= 3: 
            final_list.append(item)

    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://raw.githubusercontent.com/yqmkk/My-Live-TV/main/epg.xml"\n')
        for item in final_list:
            logo = f"https://live.fanmingming.com/tv/{item['name']}.png"
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{logo}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 强制同步 EPG
    try:
        epg = requests.get("http://epg.51zmt.top:8000/e.xml", timeout=60).content
        with open("epg.xml", "wb") as f: f.write(epg)
    except: pass
    print(f"🎉 完成！已找回并优化 {len(final_list)} 个频道。")

if __name__ == "__main__":
    main()
