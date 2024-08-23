import os
from docx import Document

# 设置目录
word_dir = "C:/Users/f1TZOF-/Downloads/China_Law_Database/sfjs/word"
txt_dir = "C:/Users/f1TZOF-/Downloads/China_Law_Database/sfjs/txt"
merged_txt_file = os.path.join(txt_dir, "merged_output.txt")

# 如果 txt 目录不存在，创建该目录
os.makedirs(txt_dir, exist_ok=True)

def docx_to_txt(docx_file, txt_file):
    try:
        print(f"正在处理文件: {docx_file}")  # 打印当前正在处理的文件
        doc = Document(docx_file)
        with open(txt_file, 'w', encoding='utf-8') as f:
            for para in doc.paragraphs:
                f.write(para.text + '\n')
        print(f"转换成功: {docx_file} -> {txt_file}")
    except Exception as e:
        print(f"转换失败: {docx_file}, 错误: {str(e)}")
        return False  # 返回失败

    return True  # 返回成功

def merge_txt_files(output_file, txt_files, chunk_size=8 * 1024 * 1024):
    current_size = 0
    part_num = 1
    current_file = None

    for txt_file in txt_files:
        try:
            with open(txt_file, 'r', encoding='utf-8') as infile:
                for line in infile:
                    if current_file is None or current_size + len(line) > chunk_size:
                        if current_file:
                            current_file.close()
                        current_file_name = f"{os.path.splitext(output_file)[0]}_part{part_num}.txt"
                        current_file = open(current_file_name, 'w', encoding='utf-8')
                        part_num += 1
                        current_size = 0
                        print(f"正在创建分片文件: {current_file_name}")
                    
                    current_file.write(line)
                    current_size += len(line)

                current_file.write("\n\n")
                current_size += 2  # 考虑到添加的间隔行

        except FileNotFoundError:
            print(f"文件未找到，跳过: {txt_file}")

    if current_file:
        current_file.close()

    print(f"所有txt文件已合并并分片为: {part_num - 1} 个文件")

def main():
    # 获取word目录中的所有docx文件
    docx_files = [f for f in os.listdir(word_dir) if f.endswith('.docx')]
    txt_files = []
    
    # 将每个docx文件转换为txt文件并存储到txt目录
    for docx_file in docx_files:
        docx_path = os.path.join(word_dir, docx_file)
        txt_file = os.path.join(txt_dir, os.path.splitext(docx_file)[0] + '.txt')
        if docx_to_txt(docx_path, txt_file):  # 如果转换成功，才加入到txt_files列表
            txt_files.append(txt_file)
    
    # 合并所有txt文件为一个文件并分片
    merge_txt_files(merged_txt_file, txt_files)

if __name__ == "__main__":
    main()
