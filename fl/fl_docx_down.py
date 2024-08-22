import os
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置下载目录
download_dir = "C:/Users/f1TZOF-/Downloads/Documents/fl"

def download_file(url, dest_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 检查请求是否成功
        with open(dest_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"文件下载成功: {dest_path}")
    except requests.exceptions.RequestException as e:
        print(f"下载文件失败: {url}, 错误: {str(e)}")

def download_with_delay(entry):
    title = entry.get('title')
    download_link = entry.get('download_link')
    if download_link:
        file_name = os.path.basename(download_link)
        file_path = os.path.join(download_dir, file_name)
        print(f"开始下载: {title}")
        download_file(download_link, file_path)
        
        # 增加下载之间的延迟，防止文件损坏
        time.sleep(5)  # 设置延迟为2秒，可以根据需要调整时间

def main():
    # 从fl_down.json文件中读取下载链接
    json_file = os.path.join(download_dir, 'fl_down.json')
    with open(json_file, 'r', encoding='utf-8') as file:
        links = json.load(file)
    
    # 使用 ThreadPoolExecutor 进行多线程下载
    max_workers = 1  # 设置线程数量，可以根据系统性能进行调整
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(download_with_delay, entry) for entry in links]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"线程下载时发生错误: {str(e)}")

if __name__ == "__main__":
    main()
