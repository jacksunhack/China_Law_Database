import json
import os

# 设置路径
download_dir = "C:/Users/f1TZOF-/Downloads/Documents/fl"
links_file = os.path.join(download_dir, 'fl_links.json')
fl_down_file = os.path.join(download_dir, 'fl_down.json')
output_dir = download_dir  # 用于保存文本文件的目录

def load_links():
    """加载所有原始链接并输出调试信息"""
    with open(links_file, 'r', encoding='utf-8') as file:
        try:
            data = json.load(file)
            print(f"Successfully loaded {len(data)} entries from fl_links.json")
            return data
        except json.JSONDecodeError as e:
            print(f"Error reading fl_links.json: {str(e)}")
            return []

def load_downloaded_links():
    """加载通过二维码识别得到的下载链接"""
    if os.path.exists(fl_down_file):
        with open(fl_down_file, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                return data
            except json.JSONDecodeError:
                return []
    return []

def normalize_title(title):
    """标准化title用于比较"""
    return title.strip().lower()

def get_txt_filenames():
    """获取所有txt文件的名字（不包括后缀），并标准化处理"""
    txt_filenames = []
    for filename in os.listdir(output_dir):
        if filename.endswith(".txt"):
            normalized_name = normalize_title(filename[:-4])  # 去掉.txt后缀并标准化
            txt_filenames.append(normalized_name)
            print(f"Found txt file: {normalized_name}")
    return txt_filenames

def find_missing_titles():
    """查找fl_links.json中缺失的标题"""
    all_links = load_links()
    downloaded_links = load_downloaded_links()
    txt_filenames = get_txt_filenames()

    # 标题列表，不去重
    all_titles = [normalize_title(link['title']) for link in all_links]
    downloaded_titles = [normalize_title(entry['title']) for entry in downloaded_links]

    print(f"Total titles in fl_links.json: {len(all_titles)}")
    print(f"Total titles in fl_down.json: {len(downloaded_titles)}")
    print(f"Total txt files: {len(txt_filenames)}")

    # 合并已处理的条目
    processed_titles = downloaded_titles + txt_filenames

    # 找出缺失的条目
    missing_titles = []
    for title in all_titles:
        if title not in processed_titles:
            missing_titles.append(title)
            print(f"Missing: {title}")
        else:
            print(f"Processed: {title}")

    return missing_titles

def main():
    missing_titles = find_missing_titles()
    if missing_titles:
        print(f"缺失了 {len(missing_titles)} 个条目：")
        for title in missing_titles:
            print(f"Missing: {title}")
    else:
        print("所有条目已成功处理。")

if __name__ == "__main__":
    main()
