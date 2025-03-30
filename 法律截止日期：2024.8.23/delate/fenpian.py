import os

# 文件路径
input_file = "fl\merged_output_part1.txt"
output_dir = "output_parts"
chunk_size = 8 * 1024 * 1024  # 8MB

# 创建输出目录
os.makedirs(output_dir, exist_ok=True)

def split_file(input_file, output_dir, chunk_size):
    with open(input_file, 'r', encoding='utf-8') as infile:
        part_num = 1
        current_size = 0
        current_file = None

        for line in infile:
            if current_file is None or current_size + len(line.encode('utf-8')) > chunk_size:
                if current_file:
                    current_file.close()
                output_file = os.path.join(output_dir, f"{os.path.basename(input_file)}_part{part_num}.txt")
                current_file = open(output_file, 'w', encoding='utf-8')
                part_num += 1
                current_size = 0
                print(f"正在创建文件: {output_file}")

            current_file.write(line)
            current_size += len(line.encode('utf-8'))

        if current_file:
            current_file.close()

    print(f"文件已分割为 {part_num - 1} 个部分，保存在目录: {output_dir}")

if __name__ == "__main__":
    split_file(input_file, output_dir, chunk_size)
