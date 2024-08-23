import json

# 假设文件名为 'xzfg_down.json'
filename = 'xzfg/xzfg_down.json'

# 读取JSON文件内容
with open(filename, 'r', encoding='utf-8') as file:
    data = json.load(file)

# 使用字典去重
unique_data = {}
for entry in data:
    title = entry['title']
    if title not in unique_data:
        unique_data[title] = entry

# 将去重后的数据转换为列表
deduplicated_data = list(unique_data.values())

# 将去重后的数据写回到JSON文件（可选择新文件名保存）
output_filename = 'xzfg_down_deduplicated.json'
with open(output_filename, 'w', encoding='utf-8') as file:
    json.dump(deduplicated_data, file, ensure_ascii=False, indent=4)

print(f"去重后的数据已保存到 {output_filename}")
