from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
        try:
            # 显式等待元素可见
            title_element = WebDriverWait(row, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.l-wen'))
            )
            title = title_element.get_attribute('title')
        except TimeoutException:
            print("等待 'li.l-wen' 元素超时，跳过该行")
            continue
        except NoSuchElementException:
            print("未找到 'li.l-wen' 元素，跳过该行")
            continue

        status_element = row.find_elements(By.CSS_SELECTOR, 'td.l-sx3 h2.l-wen1')
        if status_element:
            status = status_element[-1].text.strip()
        else:
            status = ""

        if '已废止' in status:
            print(f"忽略已废止条目: {title}")
            continue

        onclick_attr = title_element.get_attribute('onclick')
        link = onclick_attr.split("('")[1].split("')")[0]
        full_link = f"https://flk.npc.gov.cn{link}"
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
    start_url = "https://flk.npc.gov.cn/sfjs.html"
    driver.get(start_url)
    time.sleep(5)  # 等待页面加载

    for page in range(1, 74):  # 假设有 68 页
        print(f"正在检查第 {page} 页的数据...")
        scrape_page()

        # 点击下一页
        if not click_next_page():
            break  # 如果翻页失败，跳出循环

        time.sleep(5)  # 等待新页面加载

    # 保存结果到 sfjs_links.json 文件
    save_links_to_file("sfjs/sfjs_links.json", all_links)

    print("爬取完成，所有有效链接已保存。")

    # 关闭浏览器
    driver.quit()

if __name__ == "__main__":
    main()
