import bibtexparser
import requests
import os
import re
import time
from urllib.parse import urlparse
import concurrent.futures
import threading

# --- 配置区域 (CONFIGURATION) ---
BIB_FILE = 'references.bib'       # 请替换为你的 .bib 文件名
OUTPUT_DIR = 'downloaded_papers'  # PDF 保存文件夹
REPORT_FILE = 'download_report.txt'
TIMEOUT_SECONDS = 30
MAX_WORKERS = 5                   # 并发下载数

# --- GOOGLE SEARCH API 配置 ---
# 请在此处填入你的 Google API Key 和 Search Engine ID (CX)
# 获取 Key: https://developers.google.com/custom-search/v1/introduction
# 获取 CX: https://cse.google.com/cse/all (创建一个搜索引擎，启用 "Image search" 或限制为全网搜索)
GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY_HERE"
GOOGLE_CSE_ID = "YOUR_SEARCH_ENGINE_ID_HERE" 

# 模拟浏览器头信息
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 打印锁，防止多线程输出混乱
print_lock = threading.Lock()

def safe_print(message):
    with print_lock:
        print(message)

def sanitize_filename(title):
    """清理标题以用作文件名"""
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    clean = clean.replace('\n', ' ').replace('\t', ' ')
    clean = ' '.join(clean.split())
    return clean[:150]

def search_google_for_pdf(title):
    """
    使用 Google Custom Search API 搜索 PDF 链接。
    搜索查询通常是: "Title" filetype:pdf
    """
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        return None, "Google API Key 未配置"

    query = f'"{title}" filetype:pdf'
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': GOOGLE_API_KEY,
        'cx': GOOGLE_CSE_ID,
        'q': query,
        'num': 3  # 获取前3个结果
    }

    try:
        # 注意：这里是同步调用，会稍微阻塞线程，但对于多线程下载来说是可以接受的
        response = requests.get(url, params=params)
        
        if response.status_code == 429:
            return None, "Google API 配额超限 (429)"
        
        response.raise_for_status()
        results = response.json()

        if 'items' not in results:
            return None, "Google 搜索未找到结果"

        for item in results['items']:
            link = item.get('link', '')
            
            # 策略 1: 直接是 PDF 结尾
            if link.lower().endswith('.pdf'):
                return link, None
            
            # 策略 2: ArXiv 链接处理
            if 'arxiv.org/abs/' in link:
                return link.replace('/abs/', '/pdf/') + ".pdf", None
            if 'arxiv.org/pdf/' in link:
                return link, None

        return None, "搜索结果中未发现明显的 PDF 链接"

    except Exception as e:
        return None, f"Google 搜索出错: {str(e)}"

def get_initial_url(entry):
    """尝试从 BibTeX 条目中直接获取 URL"""
    url = entry.get('url', '')
    eprint = entry.get('eprint', '')
    
    # 优先处理 ArXiv
    if 'arxiv.org' in url:
        return url.replace('/abs/', '/pdf/') + ".pdf"
    
    if url:
        return url
        
    if eprint:
        if 'arxiv' in eprint.lower() or entry.get('archiveprefix', '').lower() == 'arxiv':
            clean_id = eprint.replace('arXiv:', '')
            return f"https://arxiv.org/pdf/{clean_id}.pdf"

    return None

def download_file(url, filename, folder):
    """下载文件的核心逻辑"""
    try:
        if not url:
            return False, "URL 为空"

        response = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()
        # 检查是否真的是 PDF
        if 'application/pdf' not in content_type and 'octet-stream' not in content_type:
            if 'text/html' in content_type:
                return False, f"链接返回的是 HTML 页面 (可能是付费墙/登陆页)"

        file_path = os.path.join(folder, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True, None

    except requests.exceptions.RequestException as e:
        return False, str(e)

def process_entry(entry):
    """
    单个条目的处理线程
    """
    title = entry.get('title', 'Untitled_Paper')
    safe_title = sanitize_filename(title)
    filename = f"{safe_title}.pdf"
    file_path = os.path.join(OUTPUT_DIR, filename)
    
    result = {
        'success': False,
        'title': title,
        'reason': None,
        'url': None,
        'doi': entry.get('doi', 'N/A'),
        'source': 'BibTeX'
    }

    # 检查文件是否已存在
    if os.path.exists(file_path):
        safe_print(f"[跳过] 文件已存在: {safe_title[:30]}...")
        result['success'] = True
        return result

    # 1. 尝试从 BibTeX 获取链接
    url = get_initial_url(entry)

    # 2. 如果 BibTeX 没有链接，尝试 Google Search
    if not url:
        safe_print(f"搜索中: {safe_title[:30]}...")
        google_url, error = search_google_for_pdf(title)
        if google_url:
            url = google_url
            result['source'] = 'Google Search'
        else:
            result['reason'] = error or "无 URL 且搜索失败"
            safe_print(f"   -> [未找到] {safe_title[:20]}... ({result['reason']})")
            return result

    result['url'] = url
    
    # 3. 开始下载
    safe_print(f"下载中 ({result['source']}): {safe_title[:30]}...")
    success, error_msg = download_file(url, filename, OUTPUT_DIR)

    if success:
        safe_print(f"   -> [成功] {safe_title[:20]}...")
        result['success'] = True
    else:
        safe_print(f"   -> [失败] {safe_title[:20]}... : {error_msg}")
        result['reason'] = error_msg

    return result

def main():
    # 1. 设置目录
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"已创建目录: {OUTPUT_DIR}")

    # 2. 检查 Bib 文件
    if not os.path.exists(BIB_FILE):
        print(f"错误: 未找到 {BIB_FILE}。")
        # 创建测试文件
        with open(BIB_FILE, 'w', encoding='utf-8') as f:
            f.write("""
@article{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and others},
  year={2017}
}
            """)
        print(f"已创建一个测试用的 '{BIB_FILE}' (无 URL，将测试搜索功能)。请重新运行脚本。")
        return

    # 3. 解析 BibTeX
    print(f"正在解析 {BIB_FILE}...")
    try:
        with open(BIB_FILE, 'r', encoding='utf-8') as bibtex_file:
            bib_database = bibtexparser.load(bibtex_file)
    except Exception as e:
        print(f"解析 BibTeX 失败: {e}")
        return

    total_entries = len(bib_database.entries)
    print(f"找到 {total_entries} 个条目。启动 {MAX_WORKERS} 个线程...")
    
    if "YOUR_GOOGLE_API_KEY" in GOOGLE_API_KEY:
        print("警告: 你尚未配置 GOOGLE_API_KEY，搜索功能将不可用！")

    successful_count = 0
    failed_list = []

    # 4. 多线程处理循环
    print("\n--- 开始下载 ---\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_entry = {executor.submit(process_entry, entry): entry for entry in bib_database.entries}
        
        for future in concurrent.futures.as_completed(future_to_entry):
            try:
                res = future.result()
                if res['success']:
                    successful_count += 1
                else:
                    failed_list.append(res)
            except Exception as exc:
                safe_print(f"线程发生异常: {exc}")

    # 5. 生成报告
    print(f"\n--- 处理完成 ---")
    print(f"成功: {successful_count}/{total_entries}")
    print(f"失败: {len(failed_list)}")

    if failed_list:
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(f"下载失败报告 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            for item in failed_list:
                f.write(f"标题: {item['title']}\n")
                f.write(f"原因: {item['reason']}\n")
                f.write(f"尝试的 URL: {item['url']}\n")
                f.write(f"来源: {item['source']}\n")
                if item['doi'] != 'N/A':
                    f.write(f"DOI 链接 (手动下载): https://doi.org/{item['doi']}\n")
                f.write("-" * 40 + "\n")
        
        print(f"\n详细报告已保存至: {REPORT_FILE}")
        print("请检查报告以手动下载失败的文件。")

if __name__ == "__main__":
    main()
