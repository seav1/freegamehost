import os
import time
from playwright.sync_api import sync_playwright, Cookie

def handle_consent_popup(page, timeout=10000):
    """
    处理 Cookie 同意弹窗
    """
    try:
        # 等待同意按钮出现
        consent_button_selector = 'button.fc-cta-consent.fc-primary-button'
        print("检查是否有 Cookie 同意弹窗...")
        
        # 使用较短的超时时间，因为弹窗可能不会出现
        page.wait_for_selector(consent_button_selector, state='visible', timeout=timeout)
        print("发现 Cookie 同意弹窗，正在点击'同意'按钮...")
        page.click(consent_button_selector)
        print("已点击'同意'按钮。")
        time.sleep(2)  # 等待弹窗关闭
        return True
    except Exception as e:
        print(f"未发现 Cookie 同意弹窗或已处理过: {e}")
        return False

def add_server_time(server_url="https://panel.freegamehost.xyz/server/d09ba3f7"):
    """
    尝试登录 gamepanel2.gtxgaming.co.uk 并点击 "ADD 8 HOUR(S)" 按钮。
    优先使用 REMEMBER_WEB_COOKIE 进行会话登录，如果不存在则回退到邮箱密码登录。
    """
    # 获取环境变量
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    login_email = os.environ.get('LOGIN_EMAIL')
    login_password = os.environ.get('LOGIN_PASSWORD')

    # 检查是否提供了任何登录凭据
    if not (remember_web_cookie or (login_email and login_password)):
        print("错误: 缺少登录凭据。请设置 REMEMBER_WEB_COOKIE 或 LOGIN_EMAIL 和 LOGIN_PASSWORD 环境变量。")
        return False

    with sync_playwright() as p:
        # 在 GitHub Actions 中，通常使用 headless 模式
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # --- 尝试通过 REMEMBER_WEB_COOKIE 会话登录 ---
            if remember_web_cookie:
                print("尝试使用 REMEMBER_WEB_COOKIE 会话登录...")
                session_cookie = Cookie(
                    name='remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d',
                    value=remember_web_cookie,
                    domain='.freegamehost.xyz', # 修改为目标域名
                    path='/',
                    expires=time.time() + 3600 * 24 * 365,
                    httpOnly=True,
                    secure=True,
                    sameSite='Lax'
                )
                page.context.add_cookies([session_cookie])
                print(f"已设置 REMEMBER_WEB_COOKIE。正在访问服务器页面: {server_url}")
                
                # 增加 goto 的超时时间以应对网络或服务器响应慢的问题
                page.goto(server_url, wait_until="networkidle", timeout=60000)
                
                # 处理可能出现的 Cookie 同意弹窗
                handle_consent_popup(page)

                # 检查是否成功登录并停留在服务器页面，如果重定向到登录页则会话无效
                if "login" in page.url or "auth" in page.url:
                    print("使用 REMEMBER_WEB_COOKIE 登录失败或会话无效。将尝试使用邮箱密码登录。")
                    page.context.clear_cookies()
                    remember_web_cookie = None
                else:
                    print("REMEMBER_WEB_COOKIE 登录成功。")
                    if page.url != server_url:
                         print(f"当前URL不是预期服务器页面 ({page.url})，导航到: {server_url}")
                         page.goto(server_url, wait_until="networkidle", timeout=60000)

            # --- 如果 REMEMBER_WEB_COOKIE 不可用或失败，则回退到邮箱密码登录 ---
            if not remember_web_cookie:
                if not (login_email and login_password):
                    print("错误: REMEMBER_WEB_COOKIE 无效，且未提供 LOGIN_EMAIL 或 LOGIN_PASSWORD。无法登录。")
                    return False

                login_url = "https://panel.freegamehost.xyz/auth/login" # 确认登录页 URL
                print(f"正在访问登录页: {login_url}")
                page.goto(login_url, wait_until="networkidle", timeout=60000)
                
                # 处理 Cookie 同意弹窗（在登录页面）
                handle_consent_popup(page)

                # 登录表单元素选择器
                email_selector = 'input[name="email"]'
                password_selector = 'input[name="password"]'
                login_button_selector = 'button[type="submit"]'

                print("正在等待登录元素加载...")
                page.wait_for_selector(email_selector, timeout=30000)
                page.wait_for_selector(password_selector, timeout=30000)
                page.wait_for_selector(login_button_selector, timeout=30000)

                print("正在填充邮箱和密码...")
                page.fill(email_selector, login_email)
                page.fill(password_selector, login_password)

                print("正在点击登录按钮...")
                page.click(login_button_selector)

                try:
                    page.wait_for_url(server_url, timeout=60000)
                    print("邮箱密码登录成功，已跳转到服务器页面。")
                except Exception:
                    error_message_selector = '.alert.alert-danger, .error-message, .form-error'
                    error_element = page.query_selector(error_message_selector)
                    if error_element:
                        error_text = error_element.inner_text().strip()
                        print(f"邮箱密码登录失败: {error_text}")
                        page.screenshot(path="login_fail_error_message.png")
                    else:
                        print("邮箱密码登录失败: 未能跳转到预期页面或检测到错误信息。")
                        page.screenshot(path="login_fail_no_error.png")
                    return False

            # --- 确保当前页面是目标服务器页面 ---
            print(f"当前页面URL: {page.url}")
            if page.url != server_url:
                print(f"当前不在目标服务器页面，导航到: {server_url}")
                page.goto(server_url, wait_until="networkidle", timeout=60000)
                
                # 再次处理可能出现的弹窗
                handle_consent_popup(page)
                
                if page.url != server_url and ("login" in page.url or "auth" in page.url):
                    print("导航到服务器页面失败，可能需要重新登录或会话已过期。")
                    page.screenshot(path="server_page_nav_fail.png")
                    return False

            # --- 查找并点击 "ADD 8 HOUR(S)" 按钮 ---
            add_button_selector = 'button:has-text("ADD 8 HOUR(S)")' # 修改按钮文本
            print(f"正在查找并等待 '{add_button_selector}' 按钮")

            try:
                page.wait_for_selector(add_button_selector, state='visible', timeout=30000)
                page.click(add_button_selector)
                print("成功点击 'ADD 8 HOUR(S)' 按钮。")
                time.sleep(5)
                print("等待 5 秒后继续。")
                return True
            except Exception as e:
                print(f"未找到 'ADD 8 HOUR(S)' 按钮或点击失败: {e}")
                page.screenshot(path="extend_button_not_found.png")
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            page.screenshot(path="general_error.png")
            return False
        finally:
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
