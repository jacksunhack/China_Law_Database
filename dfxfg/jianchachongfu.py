import json
from collections import defaultdict

# 加载 JSON 文件
with open('dfxfg\dfxfg_links.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# 创建一个字典来跟踪每个title出现的次数
title_counts = defaultdict(int)

# 遍历数据，检查和修改重复的title
for entry in data:
    title = entry['title']
    title_counts[title] += 1
    if title_counts[title] > 1:
        entry['title'] = f"{title}{title_counts[title]}"

# 将修改后的数据保存回 JSON 文件
with open('dfxfg/dfxfg_links_modified.json', 'w', encoding='utf-8') as file:
    json.dump(data, file, ensure_ascii=False, indent=4)

print("修改完成，结果保存在 dfxfg_links_modified.json 文件中。")
