import os
import time
from playwright.sync_api import sync_playwright, Cookie

def wait_for_cloudflare(page, max_wait=30):
    """等待 Cloudflare 检测完成"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        content = page.content().lower()
        title = page.title().lower()
        
        # 检查是否在 Cloudflare 验证页面
        if any(keyword in content or keyword in title for keyword in 
               ["cloudflare", "checking your browser", "just a moment", "ddos protection"]):
            print(f"检测到 Cloudflare 验证，已等待 {int(time.time() - start_time)} 秒...")
            time.sleep(3)
        else:
            print("Cloudflare 检测通过")
            return True
    
    print(f"警告: Cloudflare 验证超时 ({max_wait} 秒)")
    return False

def safe_goto(page, url, max_retries=3):
    """带重试的页面导航"""
    for attempt in range(max_retries):
        try:
            print(f"尝试访问 {url} (第 {attempt + 1}/{max_retries} 次)")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 等待 Cloudflare 检测
            if wait_for_cloudflare(page, max_wait=40):
                # 等待页面完全加载
                page.wait_for_load_state("networkidle", timeout=30000)
                return True
            
        except Exception as e:
            print(f"访问失败 (尝试 {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                return False
    
    return False

def add_server_time(server_url="https://panel.freegamehost.xyz/server/d09ba3f7"):
    """
    尝试登录 freegamehost.xyz 并点击 "ADD 8 HOUR(S)" 按钮。
    优化了 Cloudflare 检测处理和错误重试机制。
    """
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    login_email = os.environ.get('LOGIN_EMAIL')
    login_password = os.environ.get('LOGIN_PASSWORD')

    if not (remember_web_cookie or (login_email and login_password)):
        print("错误: 缺少登录凭据。请设置 REMEMBER_WEB_COOKIE 或 LOGIN_EMAIL 和 LOGIN_PASSWORD 环境变量。")
        return False

    with sync_playwright() as p:
        # 优化的浏览器配置，模拟真实用户
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security'
            ]
        )
        
        # 创建上下文，设置真实的浏览器特征
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        page = context.new_page()
        
        # 移除 webdriver 标记
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 添加更多反检测特征
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        try:
            # --- 尝试通过 REMEMBER_WEB_COOKIE 会话登录 ---
            if remember_web_cookie:
                print("尝试使用 REMEMBER_WEB_COOKIE 会话登录...")
                session_cookie = Cookie(
                    name='remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    value=remember_web_cookie,
                    domain='.freegamehost.xyz',
                    path='/',
                    expires=time.time() + 3600 * 24 * 365,
                    httpOnly=True,
                    secure=True,
                    sameSite='Lax'
                )
                context.add_cookies([session_cookie])
                print(f"已设置 REMEMBER_WEB_COOKIE。正在访问服务器页面: {server_url}")
                
                if not safe_goto(page, server_url):
                    print("使用 safe_goto 访问服务器页面失败")
                    page.screenshot(path="safe_goto_fail.png")
                    return False

                # 检查是否成功登录
                if "login" in page.url or "auth" in page.url:
                    print("使用 REMEMBER_WEB_COOKIE 登录失败或会话无效。将尝试使用邮箱密码登录。")
                    context.clear_cookies()
                    remember_web_cookie = None
                else:
                    print("REMEMBER_WEB_COOKIE 登录成功。")

            # --- 如果 REMEMBER_WEB_COOKIE 不可用或失败，则回退到邮箱密码登录 ---
            if not remember_web_cookie:
                if not (login_email and login_password):
                    print("错误: REMEMBER_WEB_COOKIE 无效，且未提供 LOGIN_EMAIL 或 LOGIN_PASSWORD。无法登录。")
                    return False

                login_url = "https://panel.freegamehost.xyz/auth/login"
                print(f"正在访问登录页: {login_url}")
                
                if not safe_goto(page, login_url):
                    print("访问登录页失败")
                    page.screenshot(path="login_page_fail.png")
                    return False

                # 登录表单元素选择器
                email_selector = 'input[name="email"]'
                password_selector = 'input[name="password"]'
                login_button_selector = 'button[type="submit"]'

                print("正在等待登录元素加载...")
                page.wait_for_selector(email_selector, timeout=30000)
                
                print("正在填充邮箱和密码...")
                page.fill(email_selector, login_email)
                time.sleep(1)  # 模拟人类输入延迟
                page.fill(password_selector, login_password)
                time.sleep(1)

                print("正在点击登录按钮...")
                page.click(login_button_selector)

                # 等待登录完成
                time.sleep(5)
                wait_for_cloudflare(page, max_wait=30)

                if "login" in page.url or "auth" in page.url:
                    print("邮箱密码登录失败")
                    page.screenshot(path="email_login_fail.png")
                    return False
                
                print("邮箱密码登录成功")

            # --- 确保在目标服务器页面 ---
            if page.url != server_url:
                print(f"导航到目标服务器页面: {server_url}")
                if not safe_goto(page, server_url):
                    print("导航到服务器页面失败")
                    page.screenshot(path="navigate_server_fail.png")
                    return False

            # --- 查找并点击 "ADD 8 HOUR(S)" 按钮 ---
            add_button_selector = 'button:has-text("ADD 8 HOUR(S)")'
            print(f"正在查找 'ADD 8 HOUR(S)' 按钮...")

            try:
                page.wait_for_selector(add_button_selector, state='visible', timeout=30000)
                
                # 模拟人类操作：滚动到按钮位置
                page.evaluate(f"""
                    document.querySelector('{add_button_selector}').scrollIntoView({{
                        behavior: 'smooth',
                        block: 'center'
                    }});
                """)
                time.sleep(2)
                
                page.click(add_button_selector)
                print("成功点击 'ADD 8 HOUR(S)' 按钮。")
                time.sleep(5)
                
                # 截图确认
                page.screenshot(path="success.png")
                return True
                
            except Exception as e:
                print(f"未找到 'ADD 8 HOUR(S)' 按钮或点击失败: {e}")
                page.screenshot(path="button_not_found.png")
                
                # 打印页面内容用于调试
                print("当前页面 URL:", page.url)
                print("页面标题:", page.title())
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            page.screenshot(path="general_error.png")
            return False
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    print("开始执行添加服务器时间任务...")
    success = add_server_time()
    if success:
        print("任务执行成功。")
        exit(0)
    else:
        print("任务执行失败。")
        exit(1)
