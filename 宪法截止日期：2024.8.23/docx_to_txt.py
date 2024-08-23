import os
from docx import Document

# 设置目录
download_dir = "C:/Users/f1TZOF-/Downloads/Documents/xf"
merged_txt_file = os.path.join(download_dir, "merged_output.txt")

def docx_to_txt(docx_file, txt_file):
    try:
        doc = Document(docx_file)
        with open(txt_file, 'w', encoding='utf-8') as f:
            for para in doc.paragraphs:
                f.write(para.text + '\n')
        print(f"转换成功: {docx_file} -> {txt_file}")
    except Exception as e:
        print(f"转换失败: {docx_file}, 错误: {str(e)}")

def merge_txt_files(output_file, txt_files):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
                outfile.write("\n\n")  # 添加间隔行
    print(f"所有txt文件已合并为: {output_file}")

def main():
    # 获取目录中的所有docx文件
    docx_files = [f for f in os.listdir(download_dir) if f.endswith('.docx')]
    txt_files = []
    
    # 将每个docx文件转换为txt文件
    for docx_file in docx_files:
        docx_path = os.path.join(download_dir, docx_file)
        txt_file = os.path.join(download_dir, os.path.splitext(docx_file)[0] + '.txt')
        docx_to_txt(docx_path, txt_file)
        txt_files.append(txt_file)
    
    # 合并所有txt文件为一个文件
    merge_txt_files(merged_txt_file, txt_files)

if __name__ == "__main__":
    main()
