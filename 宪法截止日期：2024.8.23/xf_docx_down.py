import os
import json
import requests

# 设置下载目录
download_dir = "C:/Users/f1TZOF-/Downloads/Documents/xf"

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

def main():
    # 从xf_down.json文件中读取下载链接
    json_file = os.path.join(download_dir, 'xf_down.json')
    with open(json_file, 'r', encoding='utf-8') as file:
        links = json.load(file)
    
    # 遍历链接并下载文件
    for entry in links:
        title = entry.get('title')
        download_link = entry.get('download_link')
        if download_link:
            file_name = os.path.basename(download_link)
            file_path = os.path.join(download_dir, file_name)
            print(f"开始下载: {title}")
            download_file(download_link, file_path)

if __name__ == "__main__":
    main()
