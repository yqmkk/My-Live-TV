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

EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
TIMEOUT = 4
MAX_WORKERS = 60

def clean_name(name):
    """极其严格的名字清洗，用于彻底去重"""
    name = name.upper()
    # 移除所有杂质
    name = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|高清|标清|HD|SD|频道|字幕|IPV6|IPV4|PLUS|\+', '', name)
    name = name.replace('-', '').replace(' ', '').replace('综合', '')
    
    # CCTV 特殊处理
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match: return f"CCTV-{match.group(1)}"
        if "新闻" in name: return "CCTV-13"
        if "少儿" in name: return "CCTV-14"
        if "音乐" in name: return "CCTV-15"
    return name.strip()

def check_channel(channel):
    name, url = channel
    std_name = clean_name(name)
    
    # 匹配分类
    target_group = next((g for g, keys in SEARCH_KEYWORDS.items() if any(k in std_name or k in name.upper() for k in keys)), None)
    if not target_group: return None

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        start = time.time()
        # 仅请求 Header
        r = requests.get(url, timeout=TIMEOUT, stream=True, headers=headers)
        if r.status_code == 200:
            delay = time.time() - start
            return {"name": std_name, "url": url, "group": target_group, "delay": delay}
    except:
        pass
    return None

def main():
    print("🚀 开始深度去重抓取...")
    all_raw_tasks = []
    seen_urls = set()

    for s in RAW_SOURCES:
        try:
            r = requests.get(s, timeout=10)
            name = ""
            for line in r.text.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    m = re.search(r',(.+)$', line)
                    name = m.group(1) if m else ""
                elif line.startswith("http") and name:
                    if line not in seen_urls:
                        all_raw_tasks.append((name, line))
                        seen_urls.add(line)
        except: continue

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_channel, t) for t in all_raw_tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    # --- 核心去重逻辑 ---
    # 先按延迟从小到大排序
    results.sort(key=lambda x: x['delay'])
    
    unique_channels = {} # { "CCTV-1": [item1, item2], "HBO": [item1] }
    for item in results:
        name = item['name']
        if name not in unique_channels:
            unique_channels[name] = []
        # 每个频道名下只保留前 2 条最快的线
        if len(unique_channels[name]) < 2:
            unique_channels[name].append(item)

    # 展开写回 M3U
    final_output = []
    for name in unique_channels:
        final_output.extend(unique_channels[name])
    
    # 最终按分类排序
    final_output.sort(key=lambda x: (x['group'], x['name']))

    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://raw.githubusercontent.com/yqmkk/My-Live-TV/main/epg.xml"\n')
        for item in final_output:
            logo = f"https://live.fanmingming.com/tv/{item['name']}.png"
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{logo}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 同步 EPG
    try:
        epg = requests.get(EPG_SOURCE, timeout=60).content
        with open("epg.xml", "wb") as f: f.write(epg)
    except: pass
    print(f"🎉 去重完成！共保留 {len(final_output)} 个极速频道。")

if __name__ == "__main__":
    main()
