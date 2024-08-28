import os
import hashlib

def get_file_hash(file_path):
    """计算文件的SHA256哈希值"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def find_and_remove_duplicates(folder_path):
    """查找并删除文件夹中的重复文件"""
    files_hashes = {}  # 存储文件哈希值和对应的文件路径
    duplicates = []  # 存储重复文件的路径

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            file_hash = get_file_hash(file_path)

            if file_hash in files_hashes:
                duplicates.append(file_path)
            else:
                files_hashes[file_hash] = file_path

    # 删除重复文件
    for duplicate_file in duplicates:
        print(f"删除重复文件: {duplicate_file}")
        os.remove(duplicate_file)

    print(f"已删除 {len(duplicates)} 个重复文件。")

# 文件夹路径
folder_path = r"C:/Users/f1TZOF-/Downloads/China_Law_Database/dfxfg/word"  # 替换为您的文件夹路径

# 运行删除重复文件的功能
find_and_remove_duplicates(folder_path)
