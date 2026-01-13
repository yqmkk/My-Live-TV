import requests
import re
import concurrent.futures
import time

# --- 搜索与过滤配置 ---
SEARCH_KEYWORDS = {
    "🇨🇳中国频道": ["CCTV", "卫视", "数字", "电影", "剧场", "频道", "新闻", "体育", "4K"],
    "🇺🇸美国精选": ["CNN", "HBO", "FOX", "ABC", "NBC", "USA", "DISCOVERY", "MOVIES", "NETFLIX"],
    "🇯🇵日本精选": ["NHK", "BS", "NTV", "TOKYO", "FUJI", "ASAHI", "JAPAN"],
    "🇰🇷韩国精选": ["KBS", "MBC", "SBS", "TVN", "MNET", "KOREA"]
}

# 基础抓取池（包含全球聚合源）
RAW_SOURCES = [
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/billy21/Tvlist-awesome-m3u-m3u8/master/m3u/migu.m3u",
    "https://raw.githubusercontent.com/James-E-A/James-E-A.github.io/main/TV/USA.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/joevess/IPTV/main/sources/iptv_sources.m3u"
]

EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
TIMEOUT = 3
MAX_WORKERS = 250 # 进一步压榨美国服务器性能

def check_channel_quality(channel):
    name, url = channel
    name_up = name.upper()
    
    # 自动搜索关键词匹配
    target_group = None
    for group, keys in SEARCH_KEYWORDS.items():
        if any(k in name_up for k in keys):
            target_group = group
            break
    
    if not target_group:
        return None

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        start = time.time()
        # 尝试连接，stream=True 用于大吞吐量检测
        with requests.get(url, timeout=TIMEOUT, stream=True, headers=headers) as r:
            if r.status_code == 200:
                delay = time.time() - start
                std_name = name.replace("高清", "").replace("HD", "").replace("-", "").strip()
                return {
                    "name": std_name,
                    "url": url,
                    "group": target_group,
                    "delay": delay,
                    "logo": f"https://live.fanmingming.com/tv/{std_name}.png"
                }
    except:
        pass
    return None

def main():
    print("📡 启动全网自动搜索引擎...")
    raw_tasks = []
    seen_urls = set()

    # 第一步：广域搜刮
    for s in RAW_SOURCES:
        try:
            r = requests.get(s, timeout=15)
            r.encoding = 'utf-8'
            name = ""
            for line in r.text.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    m = re.search(r',(.+)$', line)
                    name = m.group(1) if m else ""
                elif line.startswith("http") and name:
                    if line not in seen_urls:
                        raw_tasks.append((name, line))
                        seen_urls.add(line)
        except: continue

    print(f"🔍 全网共搜寻到 {len(raw_tasks)} 个候选链接，开始高清急速筛选...")

    # 第二步：多线程大吞吐测速
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_channel_quality, t) for t in raw_tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    # 第三步：精选排序（同名频道保留延迟最低的前3个）
    results.sort(key=lambda x: (x['name'], x['delay']))
    final_list = []
    counts = {}
    for item in results:
        counts[item['name']] = counts.get(item['name'], 0) + 1
        if counts[item['name']] <= 3: # 每个频道最多保留3个线路，确保冗余
            final_list.append(item)

    final_list.sort(key=lambda x: (x['group'], x['name']))

    # 第四步：写出唯一 M3U 地址
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://cdn.jsdelivr.net/gh/yqmkk/My-Live-TV@main/epg.xml"\n')
        for item in final_list:
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 第五步：同步唯一节目单地址
    print("📝 同步全网节目单数据库...")
    try:
        epg = requests.get(EPG_SOURCE, timeout=60).content
        with open("epg.xml", "wb") as f:
            f.write(epg)
    except: pass

    print(f"🎉 搜索完成！共筛选出 {len(final_list)} 个极速高清全球频道。")

if __name__ == "__main__":
    main()
