import requests
import re
import os

# 1. 定义上游直播源链接（这里可以无限添加已知的优质源）
sources = [
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u"
]

def fetch_and_clean():
    all_channels = []
    seen_urls = set()

    for url in sources:
        try:
            print(f"正在抓取: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                lines = response.text.split('\n')
                current_info = ""
                for line in lines:
                    if line.startswith("#EXTINF"):
                        current_info = line
                    elif line.startswith("http"):
                        # 去重逻辑
                        if line not in seen_urls:
                            # 增强逻辑：只保留高清或特定关键词
                            # if "CCTV" in current_info or "卫视" in current_info:
                            all_channels.append(f"{current_info}\n{line}")
                            seen_urls.add(line)
        except Exception as e:
            print(f"抓取失败 {url}: {e}")

    # 2. 生成最终的 M3U 文件
    with open("live_all.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("\n".join(all_channels))
    print("更新成功：live_all.m3u")

if __name__ == "__main__":
    fetch_and_clean()
