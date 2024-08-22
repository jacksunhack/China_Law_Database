import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# 全局变量定义
all_links = []
last_action_time = time.time()

def start_browser(retries=3):
    for attempt in range(retries):
        try:
            options = webdriver.ChromeOptions()
            # options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
            options.add_argument('--disable-gpu')  # 禁用GPU加速
            options.add_argument('--no-sandbox')  # 沙盒模式
            options.add_argument('--disable-dev-shm-usage')  # 禁用/dev/shm
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--incognito')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-browser-side-navigation')
            return webdriver.Chrome(options=options)
        except WebDriverException as e:
            print(f"启动浏览器失败，重试 {attempt + 1}/{retries}: {e}")
            time.sleep(5)
    raise WebDriverException("无法启动浏览器")

def update_last_action_time():
    global last_action_time
    last_action_time = time.time()

def check_for_stall(driver, threshold=5):
    if time.time() - last_action_time > threshold:
        print("检测到程序停顿，重启浏览器...")
        return True
    return False

def jump_to_page(driver, page_number, retries=5):
    for attempt in range(retries):
        try:
            print(f"尝试跳转到第 {page_number} 页...")
            page_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.layui-laypage-skip input'))
            )
            page_input.clear()
            page_input.send_keys(str(page_number))
            
            submit_button = driver.find_element(By.CSS_SELECTOR, 'span.layui-laypage-skip button')
            driver.execute_script("arguments[0].click();", submit_button)
            
            current_page_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.layui-laypage-curr em:nth-child(2)'))
            )
            current_page = int(current_page_element.text)
            if current_page == page_number:
                print(f"成功跳转到第 {page_number} 页")
                print("页面加载成功，元素找到")
                update_last_action_time()
                return True
            else:
                print(f"警告: 目标页数是 {page_number}，但实际跳转到第 {current_page} 页，重试 {attempt + 1}/{retries}")
        except (TimeoutException, WebDriverException) as e:
            print(f"跳转到第 {page_number} 页失败，重试 {attempt + 1}/{retries}: {e}")
            time.sleep(15)
    
    print(f"跳转到第 {page_number} 页超时")
    return False

def scrape_page(driver):
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, 'tr.list-b')
        for row in rows:
            try:
                title_element = row.find_element(By.CSS_SELECTOR, 'li.l-wen')
                title = title_element.get_attribute('title')

                status_element = row.find_elements(By.CSS_SELECTOR, 'td.l-sx3 h2.l-wen1')
                status = status_element[-1].text.strip() if status_element else ""

                if '已废止' in status:
                    print(f"忽略已废止条目: {title}")
                    continue

                onclick_attr = title_element.get_attribute('onclick')
                link = onclick_attr.split("('")[1].split("')")[0]
                full_link = f"https://flk.npc.gov.cn{link}"
                all_links.append({'title': title, 'link': full_link})
                print(f"通过: {title} - {full_link}")

                update_last_action_time()

            except TimeoutException:
                print("等待 'li.l-wen' 元素超时，跳过该行")
                continue
            except NoSuchElementException:
                print("未找到 'li.l-wen' 元素，跳过该行")
                continue
    except Exception as e:
        print(f"抓取页面数据时发生错误: {e}")

def save_links_to_file(file_name, links):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=4)
    print(f"数据已保存到 '{file_name}'。")

def save_current_page(current_page):
    with open("dfxfg/current_page.txt", "w") as f:
        f.write(str(current_page))

def load_current_page():
    if os.path.exists("dfxfg/current_page.txt"):
        with open("dfxfg/current_page.txt", "r") as f:
            return int(f.read().strip())
    return 1

def load_saved_links():
    if os.path.exists("dfxfg/dfxfg_links_temp.json"):
        with open("dfxfg/dfxfg_links_temp.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def restart_browser(driver, start_url, current_page):
    """重启浏览器以释放资源，并返回到当前页面"""
    driver.quit()
    time.sleep(5)
    driver = start_browser()
    driver.get(start_url)
    if not jump_to_page(driver, current_page):
        raise WebDriverException(f"无法跳转到第 {current_page} 页，程序终止")
    return driver

def main():
    global last_action_time

    driver = start_browser()
    start_url = "https://flk.npc.gov.cn/dfxfg.html"
    driver.get(start_url)
    print("页面加载中...")

    total_pages = 2226  # 假设有 2226 页
    current_page = load_current_page()  # 加载上次保存的页码

    # 如果程序是第一次启动，则从第一页开始爬取
    if current_page == 1:
        print("首次运行，从第一页开始")
    else:
        print(f"继续从第 {current_page} 页开始")

    # 跳转到当前页码
    if not jump_to_page(driver, current_page):
        print(f"跳转到第 {current_page} 页失败，程序终止")
        return

    all_links.extend(load_saved_links())  # 加载已保存的链接

    try:
        while current_page <= total_pages:
            if check_for_stall(driver):
                driver = restart_browser(driver, start_url, current_page)

            print(f"正在检查第 {current_page} 页的数据...")

            scrape_page(driver)

            # 保存爬取到的链接到临时文件中，以防程序中断导致数据丢失
            save_links_to_file("dfxfg/dfxfg_links_temp.json", all_links)

            # 每爬取25页后重启浏览器以释放资源
            if current_page % 25 == 0:
                save_current_page(current_page)  # 保存当前页码
                driver = restart_browser(driver, start_url, current_page + 1)

            # 点击下一页并获取实际页码
            next_page = jump_to_page(driver, current_page + 1)
            if not next_page:
                print(f"翻页失败，重新加载当前页...")
                driver.refresh()
                time.sleep(5)  # 等待页面加载
                next_page = jump_to_page(driver, current_page + 1)
                if not next_page:  # 重试一次
                    print("重试翻页失败，跳出循环")
                    break  # 如果仍然翻页失败，跳出循环

            # 更新当前页码
            current_page += 1
            save_current_page(current_page)  # 保存已经完成的页码

    except WebDriverException as e:
        print(f"浏览器异常: {e}")
    finally:
        save_links_to_file("dfxfg/dfxfg_links_temp.json", all_links)  # 最终保存所有链接到临时文件
        save_current_page(current_page)  # 确保在终止时保存的是已完成的页码
        driver.quit()
        print("爬取完成，所有有效链接已保存到临时文件。")

if __name__ == "__main__":
    main()
