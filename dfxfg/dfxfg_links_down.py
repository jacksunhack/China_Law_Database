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
from selenium.common.exceptions import WebDriverException, TimeoutException
from pyzbar.pyzbar import decode
from alive_progress import alive_bar
from filelock import FileLock
from bs4 import BeautifulSoup

# 设置ChromeDriver路径和下载目录
chrome_driver_path = "C:/Program Files/Google/Chrome/Application/chromedriver.exe"
download_dir = "C:/Users/f1TZOF-/Downloads/China_Law_Database/dfxfg"
processed_links_file = os.path.join(download_dir, 'dfxfg_processed_links.json')
down_links_file = os.path.join(download_dir, 'dfxfg_down.json')

INVALID_TEXTS = ["Please enable JavaScript and refresh the page", "JavaScript is not enabled"]

def create_driver():
    service = Service(chrome_driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-javascript")
    return webdriver.Chrome(service=service, options=options)

def wait_for_page_load(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
    except TimeoutException:
        print("页面加载超时")

def capture_screenshot(driver, save_path):
    try:
        if not os.path.exists(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))
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
            iframe_element = driver.find_element(By.ID, "viewDoc")
            iframe_src = iframe_element.get_attribute("src")
            return iframe_src
        except Exception as e:
            print(f"提取 iframe 链接失败: {str(e)}，正在重试...")
            time.sleep(3)
    print("多次尝试后仍未能成功提取 iframe 链接。")
    return None

def fetch_and_save_iframe_content(driver, iframe_link, filename, original_link):
    try:
        driver.get(iframe_link)
        wait_for_page_load(driver)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        text_content = soup.get_text(separator="\n", strip=True)

        for invalid_text in INVALID_TEXTS:
            if invalid_text in text_content:
                print(f"提取到无效的文本内容: {invalid_text}")
                return False

        save_text_to_file(text_content, filename)
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

def get_qr_code_link(driver, url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            wait_for_page_load(driver)

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

    iframe_link = extract_iframe_link(driver)
    if iframe_link:
        return "无二维码", iframe_link

    print("未能检测到二维码，也未能提取到 iframe 信息。")
    return None, None

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
    processed_links.add(link)
    lock = FileLock(processed_links_file + ".lock")
    with lock:
        try:
            with open(processed_links_file, 'w', encoding='utf-8') as file:
                json.dump(list(processed_links), file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存已处理链接时发生错误：{str(e)}")

def process_single_link(driver, link, progress_bar):
    title = link['title']
    original_link = link['link']
    try:
        download_link, iframe_link = get_qr_code_link(driver, original_link)
        if download_link == "无二维码" and iframe_link:
            filename = os.path.join(download_dir, f"{title}.txt")
            success = fetch_and_save_iframe_content(driver, iframe_link, filename, original_link)
        elif download_link:
            save_download_link(title, download_link, 'dfxfg_down.json', original_link)
            save_processed_link(original_link)
            success = True
        else:
            print(f"无法获取下载链接或iframe链接: {original_link}")
            success = False

        if success:
            progress_bar()
        else:
            print(f"处理失败: {original_link}")

        return success
    except Exception as e:
        print(f"处理链接时发生错误: {str(e)}")
        print(f"处理失败: {original_link}")
        return False

def process_links_in_driver(driver, links, progress_bar):
    for link in links:
        success = process_single_link(driver, link, progress_bar)
        if not success:
            return False
        
        try:
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[0])
                for handle in driver.window_handles[1:]:
                    driver.switch_to.window(handle)
                    driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except WebDriverException:
            print("浏览器连接已断开，正在重新初始化...")
            return False

        gc.collect()
    return True

def process_link_batches(links, progress_bar):
    while links:
        driver = None
        try:
            driver = create_driver()
            batch = links[:1000]
            if not process_links_in_driver(driver, batch, progress_bar):
                continue  # 如果处理失败，重新开始这个批次
            links = links[1000:]  # 移除已处理的链接
        except Exception as e:
            print(f"批次处理发生错误: {str(e)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass  # 忽略关闭driver时的错误
        time.sleep(5)  # 每个批次之间稍作暂停

def main():
    with open(os.path.join(download_dir, 'dfxfg_links.json'), 'r', encoding='utf-8') as file:
        links = json.load(file)

    processed_links = load_processed_links()
    links_to_process = [link for link in links if link['link'] not in processed_links]

    if not links_to_process:
        print("所有链接已处理完毕。")
        return

    total_links = len(links_to_process)
    
    with alive_bar(total_links, title="处理进度", force_tty=True) as progress_bar:
        process_link_batches(links_to_process, progress_bar)

    gc.collect()

if __name__ == "__main__":
    main()
