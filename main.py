import os
import time
import requests
import base64
from playwright.sync_api import sync_playwright, Cookie, TimeoutError as PlaywrightTimeoutError

def update_github_secret(secret_name, secret_value, repo_owner, repo_name, gh_pat):
    """
    使用 GitHub API 更新 Repository Secret
    """
    try:
        print(f"正在更新 GitHub Secret: {secret_name}...")
        
        # 1. 获取仓库的公钥
        public_key_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/public-key"
        headers = {
            "Authorization": f"token {gh_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(public_key_url, headers=headers)
        if response.status_code != 200:
            print(f"获取公钥失败: {response.status_code} - {response.text}")
            return False
        
        public_key_data = response.json()
        public_key = public_key_data['key']
        key_id = public_key_data['key_id']
        
        # 2. 使用 PyNaCl 加密 secret 值
        try:
            from nacl import encoding, public as nacl_public
        except ImportError:
            print("错误: 需要安装 PyNaCl 库。请运行: pip install PyNaCl")
            return False
        
        public_key_obj = nacl_public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
        sealed_box = nacl_public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        encrypted_value = base64.b64encode(encrypted).decode("utf-8")
        
        # 3. 更新 secret
        update_secret_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id
        }
        
        response = requests.put(update_secret_url, json=payload, headers=headers)
        if response.status_code in [201, 204]:
            print(f"成功更新 GitHub Secret: {secret_name}")
            return True
        else:
            print(f"更新 Secret 失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"更新 GitHub Secret 时出错: {e}")
        return False

def handle_consent_popup(page, timeout=10000):
    """
    处理 Cookie 同意弹窗
    """
    try:
        consent_button_selector = 'button.fc-cta-consent.fc-primary-button'
        print("检查是否有 Cookie 同意弹窗...")
        
        page.wait_for_selector(consent_button_selector, state='visible', timeout=timeout)
        print("发现 Cookie 同意弹窗，正在点击'同意'按钮...")
        page.click(consent_button_selector)
        print("已点击'同意'按钮。")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"未发现 Cookie 同意弹窗或已处理过")
        return False

def safe_goto(page, url, wait_until="domcontentloaded", timeout=90000):
    """
    安全的页面导航，带重试机制
    """
    max_retries = 2
    for attempt in range(max_retries):
        try:
            print(f"正在访问: {url} (尝试 {attempt + 1}/{max_retries})")
            page.goto(url, wait_until=wait_until, timeout=timeout)
            print(f"页面加载成功: {page.url}")
            
            handle_consent_popup(page, timeout=5000)
            
            return True
        except PlaywrightTimeoutError:
            print(f"页面加载超时 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                print("等待 5 秒后重试...")
                time.sleep(5)
            else:
                print("达到最大重试次数")
                return False
        except Exception as e:
            print(f"页面导航出错: {e}")
            return False
    return False

def add_server_time(server_url="https://panel.freegamehost.xyz/server/0bb0b9d6"):
    """
    尝试登录 panel.freegamehost.xyz 并点击 "ADD 8 HOURS" 按钮。
    优先使用 REMEMBER_WEB_COOKIE 进行会话登录，如果不存在则回退到邮箱密码登录。
    登录成功后自动更新 GitHub Secret 中的 REMEMBER_WEB_COOKIE。
    """
    # 获取环境变量
    remember_web_cookie = os.environ.get('REMEMBER_WEB_COOKIE')
    login_email = os.environ.get('LOGIN_EMAIL')
    login_password = os.environ.get('LOGIN_PASSWORD')
    gh_pat = os.environ.get('GH_PAT')
    github_repository = os.environ.get('GITHUB_REPOSITORY')  # 格式: owner/repo

    # 检查是否提供了任何登录凭据
    if not (remember_web_cookie or (login_email and login_password)):
        print("错误: 缺少登录凭据。请设置 REMEMBER_WEB_COOKIE 或 LOGIN_EMAIL 和 LOGIN_PASSWORD 环境变量。")
        return False

    # 解析仓库信息
    repo_owner = None
    repo_name = None
    if gh_pat and github_repository:
        try:
            repo_owner, repo_name = github_repository.split('/')
            print(f"检测到 GitHub 仓库: {repo_owner}/{repo_name}")
        except:
            print("警告: 无法解析 GITHUB_REPOSITORY，Cookie 自动更新功能将被禁用")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        cookie_updated = False

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
                
                if not safe_goto(page, server_url, wait_until="domcontentloaded"):
                    print("使用 REMEMBER_WEB_COOKIE 访问服务器页面失败。")
                    remember_web_cookie = None
                else:
                    time.sleep(3)
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
                
                if not safe_goto(page, login_url, wait_until="domcontentloaded"):
                    print("访问登录页失败。")
                    page.screenshot(path="login_page_load_fail.png")
                    return False

                email_selector = 'input[name="email"]'
                password_selector = 'input[name="password"]'
                login_button_selector = 'button[type="submit"]'

                print("正在等待登录元素加载...")
                try:
                    page.wait_for_selector(email_selector, timeout=30000)
                    page.wait_for_selector(password_selector, timeout=30000)
                    page.wait_for_selector(login_button_selector, timeout=30000)
                except Exception as e:
                    print(f"等待登录元素失败: {e}")
                    page.screenshot(path="login_elements_not_found.png")
                    return False

                print("正在填充邮箱和密码...")
                page.fill(email_selector, login_email)
                page.fill(password_selector, login_password)

                print("正在点击登录按钮...")
                page.click(login_button_selector)

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=60000)
                    time.sleep(3)
                    
                    if "login" in page.url or "auth" in page.url:
                        error_message_selector = '.alert.alert-danger, .error-message, .form-error'
                        error_element = page.query_selector(error_message_selector)
                        if error_element:
                            error_text = error_element.inner_text().strip()
                            print(f"邮箱密码登录失败: {error_text}")
                        else:
                            print("邮箱密码登录失败: 未能跳转到预期页面。")
                        page.screenshot(path="login_fail.png")
                        return False
                    else:
                        print("邮箱密码登录成功。")
                        
                        # 提取新的 remember_web cookie
                        cookies = context.cookies()
                        for cookie in cookies:
                            if cookie['name'] == 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d':
                                new_cookie_value = cookie['value']
                                print(f"提取到新的 REMEMBER_WEB_COOKIE (前20字符): {new_cookie_value[:20]}...")
                                
                                # 如果配置了 GH_PAT，则更新 GitHub Secret
                                if gh_pat and repo_owner and repo_name:
                                    if update_github_secret('REMEMBER_WEB_COOKIE', new_cookie_value, 
                                                          repo_owner, repo_name, gh_pat):
                                        cookie_updated = True
                                else:
                                    print("未配置 GH_PAT 或仓库信息，跳过 Cookie 自动更新")
                                break
                        
                        # 导航到服务器页面
                        if page.url != server_url:
                            print(f"正在导航到服务器页面: {server_url}")
                            if not safe_goto(page, server_url, wait_until="domcontentloaded"):
                                print("导航到服务器页面失败。")
                                return False
                except Exception as e:
                    print(f"登录后处理失败: {e}")
                    page.screenshot(path="post_login_error.png")
                    return False

            # --- 确保当前页面是目标服务器页面 ---
            print(f"当前页面URL: {page.url}")
            time.sleep(2)

            # --- 查找并点击 "ADD 8 HOURS" 按钮 ---
            add_button_selector = 'button:has-text("ADD 8 HOURS")'
            print(f"正在查找 'ADD 8 HOURS' 按钮...")

            try:
                page.wait_for_selector(add_button_selector, state='visible', timeout=30000)
                print("找到按钮，正在点击...")
                page.click(add_button_selector)
                print("成功点击 'ADD 8 HOURS' 按钮。")
                time.sleep(5)
                
                if cookie_updated:
                    print("✅ 任务完成，Cookie 已自动更新到 GitHub Secrets。")
                else:
                    print("✅ 任务完成。")
                return True
            except Exception as e:
                print(f"未找到 'ADD 8 HOURS' 按钮或点击失败: {e}")
                page.screenshot(path="extend_button_not_found.png")
                
                try:
                    buttons = page.query_selector_all('button')
                    print(f"页面上找到 {len(buttons)} 个按钮:")
                    for i, btn in enumerate(buttons[:10]):
                        try:
                            text = btn.inner_text().strip()
                            if text:
                                print(f"  按钮 {i+1}: {text}")
                        except:
                            pass
                except:
                    pass
                
                return False

        except Exception as e:
            print(f"执行过程中发生未知错误: {e}")
            try:
                page.screenshot(path="general_error.png")
            except:
                pass
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
