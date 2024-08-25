import json
import os
import time
import cv2
import gc
import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyzbar.pyzbar import decode
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from filelock import FileLock
from bs4 import BeautifulSoup
from contextlib import contextmanager
import asyncio
from aiohttp import ClientSession

# 设置ChromeDriver路径和下载目录
chrome_driver_path = "C:/Program Files/Google/Chrome/Application/chromedriver.exe"
download_dir = "C:/Users/f1TZOF-/Downloads/China_Law_Database/dfxfg"
processed_links_file = os.path.join(download_dir, 'dfxfg_processed_links.json')

INVALID_TEXTS = ["Please enable JavaScript and refresh the page", "JavaScript is not enabled"]

@contextmanager
def managed_driver():
    service = Service(chrome_driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-javascript")  # 确保 JavaScript 启用
    options.add_argument("--headless")  # 无头模式，避免显示浏览器界面
    driver = webdriver.Chrome(service=service, options=options)
    try:
        yield driver
    finally:
        driver.quit()
        gc.collect()  # 触发垃圾回收

def wait_for_page_load(driver, timeout=20):
    print("加载页面中...")
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )
    print("页面已加载完毕")

def capture_screenshot(driver, save_path):
    try:
        if not os.path.exists(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))  # 如果目录不存在，创建目录
        driver.save_screenshot(save_path)
        return save_path
    except Exception as e:
        print(f"截取屏幕截图失败: {str(e)}")
        return None

def decode_qr_code(image_path):
    if not os.path.exists(image_path):
        print(f"文件路径不存在: {image_path}")
        return None
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"无法读取图片文件: {image_path}")
            return None
        decoded_objects = decode(img)
        for obj in decoded_objects:
            qr_data = obj.data.decode('utf-8')
            return qr_data
        print("未检测到二维码。")
    except Exception as e:
        print(f"二维码识别失败: {str(e)}")
    return None

def extract_iframe_link(driver, retries=3):
    for attempt in range(retries):
        try:
            print("正在获取 iframe 中的链接...")
            iframe_element = driver.find_element(By.ID, "viewDoc")
            iframe_src = iframe_element.get_attribute("src")
            return iframe_src
        except Exception as e:
            print(f"提取 iframe 链接失败: {str(e)}，正在重试...")
            time.sleep(3)  # 重试前等待
    print("多次尝试后仍未能成功提取 iframe 链接。")
    return None

def fetch_and_save_iframe_content(iframe_link, filename, original_link):
    with managed_driver() as driver:
        try:
            print(f"请求 iframe 链接内容：{iframe_link}")
            driver.get(iframe_link)
            wait_for_page_load(driver)  # 确保页面完全加载

            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            text_content = soup.get_text(separator="\n", strip=True)

            # 检查提取的文本是否无效
            for invalid_text in INVALID_TEXTS:
                if invalid_text in text_content:
                    print(f"提取到无效的文本内容: {invalid_text}")
                    return False

            save_text_to_file(text_content, filename)
            # 保存成功处理的链接
            save_processed_link(original_link)
            return True
        except Exception as e:
            print(f"请求 iframe 链接内容失败: {str(e)}")
            return False

def save_text_to_file(text, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"文本内容已保存到文件：{filename}")
    except Exception as e:
        print(f"保存文本内容到文件失败：{str(e)}")

def get_qr_code_link(url, retries=3):
    with managed_driver() as driver:
        try:
            for attempt in range(retries):
                try:
                    print(f"正在处理链接: {url}")
                    driver.get(url)
                    wait_for_page_load(driver)  # 确保页面完全加载

                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )

                    screenshot_path = os.path.join(download_dir, "screenshot.png")
                    capture_screenshot(driver, screenshot_path)
                    qr_link = decode_qr_code(screenshot_path)
                    if qr_link:
                        return qr_link, None
                    else:
                        print("二维码未显示，重试中...")
                        time.sleep(10)
                except Exception as e:
                    print(f"获取二维码链接时发生错误: {str(e)}")

            # 如果仍然没有检测到二维码，尝试提取 iframe 中的链接并抓取内容
            iframe_link = extract_iframe_link(driver)
            if iframe_link:
                return "无二维码", iframe_link
        except Exception as e:
            print(f"初始化 WebDriver 时发生错误: {str(e)}")
        finally:
            driver.quit()  # 确保 WebDriver 进程被关闭
            gc.collect()  # 触发垃圾回收

    print("未能检测到二维码，也未能提取到 iframe 信息。")
    return "无二维码", None

def save_download_link(title, download_link, filename, original_link=None):
    filepath = os.path.join(download_dir, filename)
    lock = FileLock(filepath + ".lock")
    with lock:
        try:
            if not os.path.exists(filepath):
                data = []
            else:
                with open(filepath, 'r', encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError:
                        data = []

            entry = {"title": title, "download_link": download_link}
            if original_link:
                entry['original_link'] = original_link
            data.append(entry)

            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

            print(f"下载链接已保存：{title} -> {download_link}")
        except Exception as e:
            print(f"保存下载链接失败：{str(e)}")

def load_processed_links():
    """加载已处理的链接"""
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
    """保存已处理的链接"""
    processed_links = load_processed_links()
    processed_links.add(link)
    lock = FileLock(processed_links_file + ".lock")
    with lock:
        with open(processed_links_file, 'w', encoding='utf-8') as file:
            json.dump(list(processed_links), file, ensure_ascii=False, indent=4)

async def process_link_async(link):
    title = link['title']
    original_link = link['link']
    download_link, iframe_link = get_qr_code_link(original_link)
    if download_link == "无二维码" and iframe_link:
        # 请求 iframe 链接中的内容并保存
        filename = os.path.join(download_dir, f"{title}.txt")
        fetch_and_save_iframe_content(iframe_link, filename, original_link)
    else:
        save_download_link(title, download_link, 'dfxfg_down.json', original_link)
        save_processed_link(original_link)

async def monitor_and_cleanup():
    """监控和清理无效的子进程"""
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        if proc.info['name'] == 'chromedriver' and proc.info['status'] == psutil.STATUS_ZOMBIE:
            try:
                proc.terminate()
                print(f"清理僵尸进程: PID {proc.info['pid']}")
            except psutil.NoSuchProcess:
                pass

async def main_async(max_workers):
    with open(os.path.join(download_dir, 'dfxfg_links.json'), 'r', encoding='utf-8') as file:
        links = json.load(file)

    processed_links = load_processed_links()
    links_to_process = [link for link in links if link['link'] not in processed_links]

    if not links_to_process:
        print("所有链接已处理完毕。")
        return

    progress_bar = tqdm(total=len(links_to_process), desc="总进度", unit="链接")
    semaphore = asyncio.Semaphore(max_workers)  # 控制最大并发量

    async def process_with_semaphore(link):
        async with semaphore:
            await process_link_async(link)
            progress_bar.update(1)
            await monitor_and_cleanup()

    tasks = [process_with_semaphore(link) for link in links_to_process]
    await asyncio.gather(*tasks)

    progress_bar.close()
    gc.collect()  # 结束时再次触发垃圾回收，确保资源释放

if __name__ == "__main__":
    max_workers = int(input("请输入要使用的最大并发数："))
    asyncio.run(main_async(max_workers))
