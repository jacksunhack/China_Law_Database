from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

# 初始化浏览器
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
driver = webdriver.Chrome(options=options)

# 初始化一个空列表来保存所有的链接数据
all_links = []

def scrape_page():
    # 查找所有包含法规信息的行
    rows = driver.find_elements(By.CSS_SELECTOR, 'tr.list-b')

    for row in rows:
        # 获取时效性信息
        status_element = row.find_elements(By.CSS_SELECTOR, 'td.l-sx3 h2.l-wen1')
        
        # 确保 status_element 列表不为空并获取最后一个 h2 标签的内容
        if status_element:
            status = status_element[-1].text.strip()
        else:
            status = ""

        # 过滤“已废止”条目
        if '已废止' in status:
            title = row.find_element(By.CSS_SELECTOR, 'li.l-wen').get_attribute('title')
            print(f"忽略已废止条目: {title}")
            continue  # 跳过已废止的法规

        # 获取标题和链接
        title_element = row.find_element(By.CSS_SELECTOR, 'li.l-wen')
        title = title_element.get_attribute('title')
        onclick_attr = title_element.get_attribute('onclick')
        link = onclick_attr.split("('")[1].split("')")[0]
        full_link = f"https://flk.npc.gov.cn{link}"

        # 添加到结果列表
        all_links.append({'title': title, 'link': full_link})
        print(f"通过: {title} - {full_link}")

def click_next_page():
    try:
        # 等待“下一页”按钮出现，并点击它
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.layui-laypage-next'))
        )
        next_button.click()
        return True
    except Exception as e:
        print(f"翻页失败: {e}")
        return False

def save_links_to_file(file_name, links):
    # 保存文件
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=4)
    print(f"数据已保存到 '{file_name}'。")

def main():
    # 打开起始页面
    start_url = "https://flk.npc.gov.cn/xzfg.html"
    driver.get(start_url)
    time.sleep(2)  # 等待页面加载

    for page in range(1, 74):  # 假设有 68 页
        print(f"正在检查第 {page} 页的数据...")
        scrape_page()

        # 点击下一页
        if not click_next_page():
            break  # 如果翻页失败，跳出循环

        time.sleep(2)  # 等待新页面加载

    # 保存结果到 fl_links.json 文件
    save_links_to_file("fl_links.json", all_links)

    print("爬取完成，所有有效链接已保存。")

    # 关闭浏览器
    driver.quit()

if __name__ == "__main__":
    main()
