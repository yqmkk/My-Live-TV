import requests
import re
import concurrent.futures
import time

# --- 全球顶级源集合 ---
SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://iptv-org.github.io/iptv/index.m3u", # 全球最全源
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/billy21/Tvlist-awesome-m3u-m3u8/master/m3u/migu.m3u"
]

# 节目单源
EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
LOGO_BASE = "https://live.fanmingming.com/tv/"

# 测速配置
TIMEOUT = 2  # 美国服务器到全球，2秒不通必是死链
MAX_WORKERS = 200 # 美国服务器性能强，开启200线程极速清洗

def get_std_name(name):
    """强制标准化，确保能对上节目单"""
    name = name.upper()
    name = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|高清|标清|HD|SD|频道|字幕|IPV6|IPV4|-| ', '', name)
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match: return f"CCTV-{match.group(1)}"
        if "新闻" in name: return "CCTV-13"
    return name.strip()

def check_url(channel):
    name, url = channel
    std_name = get_std_name(name)
    try:
        # 模拟真实播放器，避开反爬
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        # 增加 stream=True 只读头部，极速测速
        with requests.get(url, timeout=TIMEOUT, stream=True, headers=headers) as r:
            if r.status_code == 200:
                # 智能分类
                if "CCTV" in std_name: group = "🇨🇳央视频道"
                elif any(x in std_name for x in ["卫视", "凤凰", "TVB"]): group = "🇭🇰华语卫星"
                elif any(x in std_name for x in ["HBO", "CNN", "BBC", "FOX", "DISCOVERY", "MOVIE"]): group = "🌎全球影视新闻"
                elif any(x in std_name for x in ["体育", "SPORT", "NBA"]): group = "⚽体育频道"
                else: group = "🌐全球其他"
                
                return {
                    "name": std_name,
                    "raw_name": name,
                    "url": url,
                    "group": group,
                    "logo": f"{LOGO_BASE}{std_name}.png"
                }
    except:
        pass
    return None

def main():
    print("🚀 开始全球高清源大搜刮...")
    all_tasks = []
    seen_urls = set()

    for s in SOURCES:
        try:
            r = requests.get(s, timeout=15)
            r.encoding = 'utf-8'
            temp_name = ""
            for line in r.text.split('\n'):
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r',(.+)$', line)
                    temp_name = match.group(1) if match else ""
                elif line.startswith("http") and temp_name:
                    if line not in seen_urls:
                        all_tasks.append((temp_name, line))
                        seen_urls.add(line)
        except: continue

    print(f"📡 原始链接总数: {len(all_tasks)}。美国服务器正在进行全网测速...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, t) for t in all_tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: results.append(res)

    # 排序
    results.sort(key=lambda x: (x['group'], x['name']))

    # 1. 生成 M3U（单独订阅用）
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        # 这里指定本地加速后的 EPG 地址
        f.write(f'#EXTM3U x-tvg-url="https://cdn.jsdelivr.net/gh/yqmkk/My-Live-TV@main/epg.xml"\n')
        for item in results:
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 2. 生成本地 EPG 缓存（单独订阅用）
    print("📝 同步全球节目单并进行本地化加速...")
    try:
        epg_data = requests.get(EPG_SOURCE, timeout=60).content
        with open("epg.xml", "wb") as f:
            f.write(epg_data)
        print("✅ 节目单同步成功")
    except Exception as e:
        print(f"❌ 节目单同步失败: {e}")

    print(f"🎉 任务完成！当前共筛选出 {len(results)} 个流畅频道。")

if __name__ == "__main__":
    main()
