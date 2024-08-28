import os
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import RequestException
import random
import urllib.parse
from tqdm import tqdm

# 设置下载目录
download_dir = "C:/Users/f1TZOF-/Downloads/China_Law_Database/dfxfg/word"

# 如果目录不存在，创建目录
os.makedirs(download_dir, exist_ok=True)

# 代理设置
proxies = {
    'http': 'socks5://t12472272965911:gu113bgx@e298.kdltps.com:20818',
    'https': 'socks5://t12472272965911:gu113bgx@e298.kdltps.com:20818'
}

# 备用代理
backup_proxies = {
    'http': 'socks5://t12472272965911:gu113bgx@e299.kdltps.com:20818',
    'https': 'socks5://t12472272965911:gu113bgx@e299.kdltps.com:20818'
}

# 模仿 wget 的 User-Agent
user_agent = "Wget/1.21.3"

def check_existing_file(download_link):
    expected_filename = os.path.basename(urllib.parse.urlparse(download_link).path)
    for filename in os.listdir(download_dir):
        if filename.endswith(expected_filename):
            return os.path.join(download_dir, filename)
    return None

def download_file(url, dest_path, max_retries=10):
    headers = {
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "Keep-Alive",
    }
    
    for attempt in range(max_retries):
        try:
            current_proxies = proxies if attempt % 2 == 0 else backup_proxies
            with requests.get(url, stream=True, proxies=current_proxies, headers=headers, timeout=30) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(dest_path, 'wb') as file, tqdm(
                    desc=os.path.basename(dest_path),
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as progress_bar:
                    for data in response.iter_content(chunk_size=1024):
                        size = file.write(data)
                        progress_bar.update(size)
                
                print(f"文件下载成功: {dest_path}")
            return True
        except RequestException as e:
            print(f"下载文件失败: {url}, 错误: {str(e)}, 尝试次数: {attempt + 1}")
            time.sleep(random.uniform(5, 15))  # 增加等待时间
    
    print(f"文件下载失败，已达到最大重试次数: {url}")
    return False

def download_with_retry(entry):
    title = entry.get('title')
    download_link = entry.get('download_link')
    if download_link:
        existing_file = check_existing_file(download_link)
        if existing_file:
            return title, "已存在", existing_file

        file_name = urllib.parse.unquote(os.path.basename(download_link))
        file_path = os.path.join(download_dir, file_name)
        print(f"开始下载: {title}")
        
        for attempt in range(3):  # 最多尝试3次
            success = download_file(download_link, file_path)
            if success:
                return title, "下载成功", file_path
            print(f"重新尝试下载: {title}")
        
        return title, "下载失败", None
    return title, "无下载链接", None

def main():
    # 从dfxfg_down.json文件中读取下载链接
    json_file = os.path.join(download_dir, '../dfxfg_down.json')
    with open(json_file, 'r', encoding='utf-8') as file:
        links = json.load(file)
    
    results = []
    max_workers = 5  # 设置线程数量，可以根据系统性能进行调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_with_retry, entry) for entry in links]
        
        for future in tqdm(as_completed(futures), total=len(links), desc="总进度"):
            result = future.result()
            results.append(result)
            print(f"完成处理: {result[0]}, 状态: {result[1]}")

    # 生成报告
    success_count = sum(1 for r in results if r[1] == "下载成功")
    existing_count = sum(1 for r in results if r[1] == "已存在")
    fail_count = sum(1 for r in results if r[1] == "下载失败")
    no_link_count = sum(1 for r in results if r[1] == "无下载链接")

    print("\n下载报告:")
    print(f"总链接数: {len(links)}")
    print(f"成功下载: {success_count}")
    print(f"已存在文件: {existing_count}")
    print(f"下载失败: {fail_count}")
    print(f"无下载链接: {no_link_count}")

    # 保存失败的下载信息
    failed_downloads = [r for r in results if r[1] == "下载失败"]
    if failed_downloads:
        with open('failed_downloads.json', 'w', encoding='utf-8') as f:
            json.dump(failed_downloads, f, ensure_ascii=False, indent=2)
        print(f"失败的下载信息已保存到 failed_downloads.json")

    # 保存所有下载结果
    with open('download_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"所有下载结果已保存到 download_results.json")

if __name__ == "__main__":
    main()
