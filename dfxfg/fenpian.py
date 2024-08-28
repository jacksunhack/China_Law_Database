import os

# 设置目录
txt_dir = r"C:/Users/f1TZOF-/Downloads/China_Law_Database/dfxfg/txt"
output_file = os.path.join(txt_dir, "../merged_output.txt")
chunk_size = 8 * 1024 * 1024  # 8 MB

def merge_and_split_txt_files(txt_dir, output_file, chunk_size):
    current_size = 0
    part_num = 1
    current_file = None

    def open_new_part():
        nonlocal current_file, current_size, part_num
        if current_file:
            current_file.close()
        current_file_name = f"{os.path.splitext(output_file)[0]}_part{part_num}.txt"
        current_file = open(current_file_name, 'w', encoding='utf-8')
        part_num += 1
        current_size = 0
        print(f"正在创建分片文件: {current_file_name}")

    open_new_part()

    # 获取目录中的所有txt文件
    txt_files = [os.path.join(txt_dir, f) for f in os.listdir(txt_dir) if f.endswith('.txt')]

    for txt_file in txt_files:
        try:
            with open(txt_file, 'r', encoding='utf-8') as infile:
                for line in infile:
                    encoded_line = line.encode('utf-8')
                    line_size = len(encoded_line)
                    
                    if current_size + line_size > chunk_size:
                        open_new_part()

                    current_file.write(line)
                    current_size += line_size

                current_file.write("\n")  # 文件之间添加换行符
                current_size += 1  # 换行符大小
        except FileNotFoundError:
            print(f"文件未找到，跳过: {txt_file}")

    if current_file:
        current_file.close()

    print(f"所有txt文件已合并并分片为: {part_num - 1} 个文件")

if __name__ == "__main__":
    merge_and_split_txt_files(txt_dir, output_file, chunk_size)
