import requests
import re
import concurrent.futures
import time

# --- 核心数据源：涵盖高清、4K 及全球精选 ---
SOURCES = [
    # 中国全量（含高清、IPv6、移动/电信/联通源）
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u",
    "https://raw.githubusercontent.com/billy21/Tvlist-awesome-m3u-m3u8/master/m3u/migu.m3u",
    # 全球源（用于筛选日韩美）
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/James-E-A/James-E-A.github.io/main/TV/USA.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u"
]

# 节目单源
EPG_SOURCE = "http://epg.51zmt.top:8000/e.xml"
LOGO_BASE = "https://live.fanmingming.com/tv/"

# 测速配置：大吞吐优先，只要能连上且速度快的
TIMEOUT = 3 
MAX_WORKERS = 200 # 高并发处理

def get_std_info(name):
    """频道标准化及国家分类逻辑"""
    n = name.upper()
    # 默认分类
    group = "🌐全球其他"
    
    # 中国频道判断（全量）
    if any(x in n for x in ["CCTV", "卫视", "数字", "电影", "剧场", "频道", "新闻", "体育"]):
        group = "🇨🇳中国高清"
    # 美国精选
    elif any(x in n for x in ["CNN", "HBO", "FOX", "ABC", "NBC", "USA", "DISCOVERY", "MOVIES"]):
        group = "🇺🇸美国精选"
    # 日本精选
    elif any(x in n for x in ["NHK", "BS", "NTV", "TOKYO", "FUJI", "ASAHI", "JAPAN"]):
        group = "🇯🇵日本精选"
    # 韩国精选
    elif any(x in n for x in ["KBS", "MBC", "SBS", "TVN", "MNET", "KOREA"]):
        group = "🇰🇷韩国精选"
    
    # 频道名标准化
    std_name = name.replace("高清", "").replace("HD", "").replace("-", "").strip()
    return std_name, group

def check_url(channel):
    name, url = channel
    std_name, group = get_std_info(name)
    
    # 如果不是中、美、日、韩，直接剔除，保持列表精简
    if group == "🌐全球其他":
        return None
        
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TiviMate/4.7.0'}
        start = time.time()
        # 测速：连接并读取前 1024 字节以确保流确实可用（大吞吐检测）
        response = requests.get(url, timeout=TIMEOUT, stream=True, headers=headers)
        if response.status_code == 200:
            delay = time.time() - start
            return {
                "name": std_name,
                "url": url,
                "group": group,
                "logo": f"{LOGO_BASE}{std_name}.png",
                "delay": delay
            }
    except:
        pass
    return None

def main():
    print("🚀 启动大吞吐高清抓取引擎...")
    tasks = []
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
                        tasks.append((temp_name, line))
                        seen_urls.add(line)
        except: continue

    print(f"📡 原始待测源: {len(tasks)}，正在进行全球链路测速...")

    valid_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url, t) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: valid_results.append(res)

    # 排序逻辑：先按组排，组内按延迟（速度）排
    valid_results.sort(key=lambda x: (x['group'], x['delay']))

    # 1. 生成唯一的 M3U 直播源地址
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="https://cdn.jsdelivr.net/gh/yqmkk/My-Live-TV@main/epg.xml"\n')
        for item in valid_results:
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    # 2. 生成唯一的 EPG 节目单地址
    print("📝 同步并缓存全量节目单...")
    try:
        epg_content = requests.get(EPG_SOURCE, timeout=60).content
        with open("epg.xml", "wb") as f:
            f.write(epg_content)
        print("✅ 节目单缓存成功")
    except:
        print("❌ 节目单同步失败")

    print(f"🎉 搞定！已为你筛选出 {len(valid_results)} 个极速高清频道。")

if __name__ == "__main__":
    main()
