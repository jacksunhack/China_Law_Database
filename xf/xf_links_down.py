import json
import os
import time
import cv2
import gc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyzbar.pyzbar import decode
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置ChromeDriver路径和下载目录
chrome_driver_path = "C:/Program Files/Google/Chrome/Application/chromedriver.exe"
download_dir = "C:/Users/f1TZOF-/Downloads/Documents/xf"
processed_links_file = os.path.join(download_dir, 'xf_processed_links.json')

def setup_driver():
    service = Service(chrome_driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless")  # 无头模式，避免显示浏览器界面
    return webdriver.Chrome(service=service, options=options)

def capture_screenshot(driver, save_path):
    try:
        driver.save_screenshot(save_path)
        return save_path
    except Exception as e:
        print(f"截取屏幕截图失败: {str(e)}")
        return None

def decode_qr_code(image_path):
    try:
        img = cv2.imread(image_path)
        decoded_objects = decode(img)
        for obj in decoded_objects:
            qr_data = obj.data.decode('utf-8')
            return qr_data
    except Exception as e:
        print(f"二维码识别失败: {str(e)}")
    return None

def get_qr_code_link(driver, url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            screenshot_path = os.path.join(download_dir, "screenshot.png")
            capture_screenshot(driver, screenshot_path)
            qr_link = decode_qr_code(screenshot_path)
            if qr_link:
                return qr_link
            else:
                print("二维码未显示，重试中...")
                time.sleep(15)
        except Exception as e:
            print(f"获取二维码链接时发生错误: {str(e)}")
    print("未能检测到二维码，将其标记为无二维码")
    return "无二维码"

def save_download_link(title, download_link, filename):
    filepath = os.path.join(download_dir, filename)
    try:
        if not os.path.exists(filepath):
            data = []
        else:
            with open(filepath, 'r', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = []

        if any(entry['download_link'] == download_link for entry in data):
            print(f"下载链接已存在，跳过保存：{title} -> {download_link}")
            return

        data.append({"title": title, "download_link": download_link})
        
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        
        print(f"下载链接已保存：{title} -> {download_link}")
    except Exception as e:
        print(f"保存下载链接失败：{str(e)}")

def load_processed_links():
    if os.path.exists(processed_links_file):
        with open(processed_links_file, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                if not data:
                    return set()
                return set(data)
            except json.JSONDecodeError:
                print("JSON 文件格式不正确，返回空的已处理链接集。")
                return set()
    return set()

def save_processed_link(link):
    processed_links = load_processed_links()
    processed_links.add(link['link'])
    with open(processed_links_file, 'w', encoding='utf-8') as file:
        json.dump(list(processed_links), file, ensure_ascii=False, indent=4)

def process_link(link, progress_bar):
    driver = setup_driver()  # 在每个线程中创建一个新的浏览器驱动
    try:
        title = link['title']
        download_link = get_qr_code_link(driver, link['link'])
        save_download_link(title, download_link, 'xf_down.json' if download_link != "无二维码" else 'xf_wuqr.json')
        save_processed_link(link)
    finally:
        driver.quit()  # 处理完链接后关闭浏览器驱动
        progress_bar.update(1)

def main():
    with open(os.path.join(download_dir, 'xf_links.json'), 'r', encoding='utf-8') as file:
        links = json.load(file)

    processed_links = load_processed_links()
    links_to_process = [link for link in links if link['link'] not in processed_links]

    if not links_to_process:
        print("所有链接已处理完毕。")
        return

    max_workers = int(input("请输入要使用的最大线程数："))
    progress_bar = tqdm(total=len(links_to_process), desc="总进度", unit="链接")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_link, link, progress_bar) for link in links_to_process]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"处理链接时发生异常: {str(e)}")

        executor.shutdown(wait=True)

    progress_bar.close()

if __name__ == "__main__":
    main()
