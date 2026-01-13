import requests
import re
import concurrent.futures
import datetime

# --- 配置区 ---
SOURCES = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Guovern/tv-list/main/m3u/chinatv.m3u"
]

EPG_URL = "http://epg.51zmt.top:8000/e.xml"
LOGO_BASE = "https://live.fanmingming.com/tv/" # 使用常用高清台标库

TIMEOUT = 3
MAX_WORKERS = 60

def clean_channel_name(name):
    """标准化频道名称，去除杂质"""
    name = name.upper()
    name = re.sub(r'\[.*?\]|（.*?）|\(.*?\)', '', name) # 去除括号内容
    name = re.sub(r'高清|标清|HD|SD|频道|字幕|IPV6|IPV4', '', name)
    name = name.replace('-', '').replace(' ', '')
    
    # 常见央视缩写修复
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match:
            num = match.group(1)
            # 特殊处理 CCTV 5+, 17 等
            if num == "5P": return "CCTV5+"
            name = f"CCTV-{num}"
        elif "NEWS" in name or "新闻" in name: name = "CCTV-13"
        elif "KIDS" in name or "少儿" in name: name = "CCTV-14"
        elif "MUSIC" in name or "音乐" in name: name = "CCTV-15"
    
    return name.strip()

def get_metadata(name):
    """根据标准名获取组别和台标"""
    group = "地方/其他"
    logo = ""
    
    if "CCTV" in name:
        group = "央视频道"
        logo = f"{LOGO_BASE}{name}.png"
    elif "卫视" in name:
        group = "卫视频道"
        logo = f"{LOGO_BASE}{name}.png"
    elif any(x in name for x in ["4K", "8K"]):
        group = "超高清"
    
    return group, logo

def check_url(channel):
    """测速并返回带元数据的频道信息"""
    raw_name, url = channel
    std_name = clean_channel_name(raw_name)
    group, logo = get_metadata(std_name)
    
    try:
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code == 200:
            return {
                "name": std_name,
                "url": url,
                "group": group,
                "logo": logo
            }
    except:
        pass
    return None

def fetch_and_build():
    tasks = []
    seen_urls = set()

    print("开始获取源数据...")
    for source in SOURCES:
        try:
            r = requests.get(source, timeout=10)
            r.encoding = 'utf-8'
            lines = r.text.split('\n')
            temp_name = ""
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    match = re.search(r',(.+)$', line)
                    temp_name = match.group(1) if match else ""
                elif line.startswith("http") and temp_name:
                    if line not in seen_urls:
                        tasks.append((temp_name, line))
                        seen_urls.add(line)
        except:
            continue

    print(f"有效原始链接: {len(tasks)}，开始多线程清洗与验证...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(check_url, task): task for task in tasks}
        for future in concurrent.futures.as_completed(future_to_url):
            res = future.result()
            if res:
                results.append(res)

    # 排序：按组别然后按名称
    results.sort(key=lambda x: (x['group'], x['name']))

    # 写入 M3U
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        # 写入头部，包含 EPG 声明
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        
        for item in results:
            # 写入标准化标签：tvg-name(匹配EPG), tvg-logo(显示台标), group-title(分类)
            f.write(f'#EXTINF:-1 tvg-name="{item["name"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
            f.write(f'{item["url"]}\n')

    print(f"同步完成！生成频道: {len(results)} 个。")

if __name__ == "__main__":
    fetch_and_build()
