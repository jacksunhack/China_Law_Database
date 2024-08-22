from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import json
import time

# 设置WebDriver（使用Chrome为例）
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # 无头模式，不显示浏览器界面
driver = webdriver.Chrome(options=options)

# 打开目标网页
url = "http://flk.npc.gov.cn/xf.html"
driver.get(url)

# 等待页面加载
time.sleep(3)  # 等待页面的内容加载，具体时间可以根据需要调整

# 获取页面源代码
html_content = driver.page_source

# 使用BeautifulSoup解析HTML内容
soup = BeautifulSoup(html_content, 'html.parser')

# 找到包含内容的表格行
rows = soup.select('tbody#flData tr.list-b')

# 初始化一个列表来保存所有的链接数据
links_data = []

# 提取每一行中的数据
for row in rows:
    title_element = row.find('li', class_='l-wen')
    title = title_element.get_text(strip=True)
    link = title_element['onclick'].split("'")[1]  # 提取 onclick 里的链接
    full_link = f"http://flk.npc.gov.cn{link}"

    # 将标题和链接存入字典
    links_data.append({'title': title, 'link': full_link})

# 将结果保存到 JSON 文件
with open("xf_down.json", "w", encoding="utf-8") as f:
    json.dump(links_data, f, ensure_ascii=False, indent=4)

print("抓取完成，所有链接已保存到 xf_down.json")

# 关闭WebDriver
driver.quit()
