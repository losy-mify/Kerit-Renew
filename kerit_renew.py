import time
import imaplib
import email
import re
import subprocess
from seleniumbase import SB

# ============================================================
# 配置
# ============================================================

KERIT_EMAIL    = "ak1ra0chan9@gmail.com"
GMAIL_PASSWORD = "tvxfjefmcxrykvzu"
LOCAL_PROXY    = "http://127.0.0.1:8080"
MASKED_EMAIL   = "******@" + KERIT_EMAIL.split("@")[1]

LOGIN_URL      = "https://billing.kerit.cloud/"
FREE_PANEL_URL = "https://billing.kerit.cloud/free_panel"


# ============================================================
# IMAP 读取 Gmail OTP
# ============================================================

def fetch_otp_from_gmail(wait_seconds=60) -> str:
    print(f"📬 连接Gmail，等待{wait_seconds}s...")
    deadline = time.time() + wait_seconds

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(KERIT_EMAIL, GMAIL_PASSWORD)

    spam_folder = None
    _, folder_list = mail.list()
    for f in folder_list:
        decoded = f.decode("utf-8", errors="ignore")
        if any(k in decoded for k in ["Spam", "Junk", "垃圾", "spam", "junk"]):
            match = re.search(r'"([^"]+)"\s*$', decoded)
            if not match:
                match = re.search(r'(\S+)\s*$', decoded)
            if match:
                spam_folder = match.group(1).strip('"')
                print(f"🗑️ 垃圾箱: {spam_folder}")
                break

    folders_to_check = ["INBOX"]
    if spam_folder:
        folders_to_check.append(spam_folder)
    else:
        print("⚠️ 未找到垃圾箱")

    seen_uids = {}
    for folder in folders_to_check:
        try:
            status, _ = mail.select(folder)
            if status != "OK":
                raise Exception(f"select失败: {status}")
            _, data = mail.uid("search", None, "ALL")
            seen_uids[folder] = set(data[0].split())
        except Exception as e:
            print(f"⚠️ 文件夹异常 {folder}: {e}")
            seen_uids[folder] = set()

    while time.time() < deadline:
        time.sleep(5)

        for folder in folders_to_check:
            try:
                status, _ = mail.select(folder)
                if status != "OK":
                    continue
                _, data = mail.uid("search", None, 'FROM "kerit"')
                all_uids = set(data[0].split())
                new_uids = all_uids - seen_uids[folder]

                for uid in new_uids:
                    seen_uids[folder].add(uid)
                    _, msg_data = mail.uid("fetch", uid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                break
                        if not body:
                            for part in msg.walk():
                                if part.get_content_type() == "text/html":
                                    html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                    body = re.sub(r'<[^>]+>', ' ', html)
                                    break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                    otp = re.search(r'\b(\d{4})\b', body)
                    if otp:
                        code = otp.group(1)
                        print(f"✅ Gmail OTP: {code}")
                        mail.logout()
                        return code

            except Exception as e:
                print(f"⚠️ 检查{folder}出错: {e}")
                continue

    mail.logout()
    raise TimeoutError("❌ Gmail超时")


# ============================================================
# Turnstile 工具函数
# ============================================================

EXPAND_POPUP_JS = """
(function() {
    var turnstileInput = document.querySelector('input[name="cf-turnstile-response"]');
    if (!turnstileInput) return;
    var el = turnstileInput;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var style = window.getComputedStyle(el);
        if (style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowY === 'hidden') {
            el.style.overflow = 'visible';
        }
        el.style.minWidth = 'max-content';
    }
    var iframes = document.querySelectorAll('iframe');
    iframes.forEach(function(iframe) {
        if (iframe.src && iframe.src.includes('challenges.cloudflare.com')) {
            iframe.style.width = '300px';
            iframe.style.height = '65px';
            iframe.style.minWidth = '300px';
            iframe.style.visibility = 'visible';
            iframe.style.opacity = '1';
        }
    });
})();
"""


def xdotool_click(x, y):
    x, y = int(x), int(y)
    try:
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--class", "chrome"],
            capture_output=True, text=True, timeout=3
        )
        wids = [w for w in result.stdout.strip().split('\n') if w]
        if wids:
            subprocess.run(["xdotool", "windowactivate", wids[-1]],
                           timeout=2, stderr=subprocess.DEVNULL)
            time.sleep(0.2)
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=2, check=True)
        time.sleep(0.15)
        subprocess.run(["xdotool", "click", "1"], timeout=2, check=True)
        return True
    except Exception as e:
        print(f"⚠️ xdotool失败: {e}")
        return False


def get_turnstile_coords(sb):
    try:
        return sb.execute_script("""
            (function(){
                var iframes = document.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    var src = iframes[i].src || '';
                    if (src.includes('cloudflare') || src.includes('turnstile')) {
                        var rect = iframes[i].getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            return {
                                click_x: Math.round(rect.x + 30),
                                click_y: Math.round(rect.y + rect.height / 2)
                            };
                        }
                    }
                }
                var input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input) {
                    var container = input.parentElement;
                    for (var j = 0; j < 5; j++) {
                        if (!container) break;
                        var rect = container.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 30) {
                            return {
                                click_x: Math.round(rect.x + 30),
                                click_y: Math.round(rect.y + rect.height / 2)
                            };
                        }
                        container = container.parentElement;
                    }
                }
                return null;
            })()
        """)
    except Exception:
        return None


def get_window_offset(sb):
    try:
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--class", "chrome"],
            capture_output=True, text=True, timeout=3
        )
        wids = [w for w in result.stdout.strip().split('\n') if w]
        if wids:
            geo = subprocess.run(
                ["xdotool", "getwindowgeometry", "--shell", wids[-1]],
                capture_output=True, text=True, timeout=3
            ).stdout
            geo_dict = {}
            for line in geo.strip().split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    geo_dict[k.strip()] = int(v.strip())
            win_x = geo_dict.get('X', 0)
            win_y = geo_dict.get('Y', 0)
            info = sb.execute_script(
                "(function(){ return { outer: window.outerHeight, inner: window.innerHeight }; })()"
            )
            toolbar = info['outer'] - info['inner']
            if not (30 <= toolbar <= 200):
                toolbar = 87
            return win_x, win_y, toolbar
    except Exception:
        pass
    try:
        info = sb.execute_script("""
            (function(){
                return {
                    screenX: window.screenX || 0,
                    screenY: window.screenY || 0,
                    outer: window.outerHeight,
                    inner: window.innerHeight
                };
            })()
        """)
        toolbar = info['outer'] - info['inner']
        if not (30 <= toolbar <= 200):
            toolbar = 87
        return info['screenX'], info['screenY'], toolbar
    except Exception:
        return 0, 0, 87


def check_token(sb) -> bool:
    try:
        return sb.execute_script("""
            (function(){
                var input = document.querySelector('input[name="cf-turnstile-response"]');
                return input && input.value && input.value.length > 20;
            })()
        """)
    except Exception:
        return False


def turnstile_exists(sb) -> bool:
    try:
        return sb.execute_script(
            "(function(){ return document.querySelector('input[name=\"cf-turnstile-response\"]') !== null; })()"
        )
    except Exception:
        return False


def solve_turnstile(sb) -> bool:
    for _ in range(3):
        sb.execute_script(EXPAND_POPUP_JS)
        time.sleep(0.5)

    if check_token(sb):
        print("✅ Token已存在")
        return True

    coords = get_turnstile_coords(sb)
    if not coords:
        print("❌ 无法获取坐标")
        return False

    win_x, win_y, toolbar = get_window_offset(sb)
    abs_x = coords['click_x'] + win_x
    abs_y = coords['click_y'] + win_y + toolbar
    print(f"🖱️ 点击Token: ({abs_x}, {abs_y})")
    xdotool_click(abs_x, abs_y)

    for _ in range(30):
        time.sleep(0.5)
        if check_token(sb):
            print("✅ Cloudflare Token通过")
            return True

    print("❌ Cloudflare Token超时")
    sb.save_screenshot("turnstile_fail.png")
    return False


# ============================================================
# 续期流程
# ============================================================

def do_renew(sb):
    print("🔄 跳转续期页...")
    sb.open(FREE_PANEL_URL)
    time.sleep(4)
    sb.save_screenshot("free_panel.png")

    server_id = sb.execute_script(
        "(function(){ return typeof serverData !== 'undefined' ? serverData.id : null; })()"
    )
    if not server_id:
        print("❌ serverData.id缺失")
        sb.save_screenshot("no_server_id.png")
        return
    print(f"🆔 服务器ID: {server_id}")

    for attempt in range(7):
        count = sb.execute_script("""
            (function(){
                var el = document.getElementById('renewal-count');
                return el ? parseInt(el.innerText || "0") : 0;
            })()
        """)
        print(f"📊 续期进度: {count}/7")

        if count >= 7:
            print("🎉 已达上限7/7")
            sb.save_screenshot("renew_full.png")
            return

        print(f"🔁 第{attempt + 1}次续期...")
        try:
            sb.wait_for_element_visible('#renewServerBtn', timeout=10)
            sb.click('#renewServerBtn')
        except Exception as e:
            print(f"❌ 续期按钮缺失: {e}")
            sb.save_screenshot("no_renew_btn.png")
            return

        time.sleep(2)

        print("⏳ 等待Turnstile...")
        for _ in range(20):
            if turnstile_exists(sb):
                print("🛡️ 检测到Turnstile")
                break
            time.sleep(1)
        else:
            print("❌ Turnstile未出现")
            sb.save_screenshot(f"no_turnstile_{attempt}.png")
            return

        if not solve_turnstile(sb):
            sb.save_screenshot(f"turnstile_fail_{attempt}.png")
            return

        token = sb.execute_script("""
            (function(){
                var input = document.querySelector('input[name="cf-turnstile-response"]');
                return input ? input.value : null;
            })()
        """)
        if not token:
            print("❌ Token获取失败")
            return

        print("🎯 提交/api/renew...")
        result = sb.execute_script(f"""
            (async function() {{
                const res = await fetch('/api/renew', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    credentials: 'include',
                    body: JSON.stringify({{ id: {server_id}, captcha: '{token}' }})
                }});
                const data = await res.json();
                return JSON.stringify(data);
            }})()
        """)
        print(f"📋 续期结果: {result}")

        try:
            sb.execute_script("document.querySelector('[data-bs-dismiss=\"modal\"]')?.click();")
        except Exception:
            pass

        time.sleep(3)
        sb.execute_script("window.location.reload();")
        time.sleep(3)

    sb.save_screenshot("renew_done.png")
    print("✅ 续期完成")


# ============================================================
# 主流程
# ============================================================

def run_script():
    print("🔧 启动中...")

    with SB(uc=True, test=True, proxy=LOCAL_PROXY) as sb:
        print("🚀 浏览器就绪")

        print("🌐 验证代理...")
        try:
            sb.open("https://api.ipify.org/?format=json")
            print(f"✅ 出口IP: {sb.get_text('body')}")
        except Exception:
            print("⚠️ 代理超时，跳过")

        print("🔑 访问登录页...")
        sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=4)
        time.sleep(3)

        print("🛡️ 检查Cloudflare...")
        for _ in range(20):
            time.sleep(0.5)
            if turnstile_exists(sb):
                print("🛡️ 检测到Turnstile...")
                if not solve_turnstile(sb):
                    sb.save_screenshot("kerit_cf_fail.png")
                    return
                time.sleep(2)
                break
        else:
            print("✅ 无Turnstile，继续")

        print("📭 等待邮箱框...")
        try:
            sb.wait_for_element_visible('#email-input', timeout=20)
        except Exception:
            print("❌ 邮箱框超时")
            sb.save_screenshot("kerit_no_email_input.png")
            return

        sb.type('#email-input', KERIT_EMAIL)
        print(f"✅ 邮箱: {MASKED_EMAIL}")

        print("🖱️ 点击继续...")
        clicked = False
        for sel in [
            '//button[contains(., "Continue with Email")]',
            '//span[contains(., "Continue with Email")]',
            'button[type="submit"]',
        ]:
            try:
                if sb.is_element_visible(sel):
                    sb.click(sel)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            print("❌ 继续按钮缺失")
            sb.save_screenshot("kerit_no_continue_btn.png")
            return

        print("📨 等待OTP框...")
        try:
            sb.wait_for_element_visible('.otp-input', timeout=30)
        except Exception:
            print("❌ OTP框超时")
            sb.save_screenshot("kerit_no_otp.png")
            return

        try:
            code = fetch_otp_from_gmail(wait_seconds=60)
        except TimeoutError as e:
            print(e)
            sb.save_screenshot("kerit_otp_timeout.png")
            return

        otp_inputs = sb.find_elements('.otp-input')
        if len(otp_inputs) < 4:
            print(f"❌ OTP框不足: {len(otp_inputs)}")
            return

        print(f"⌨️ 填入OTP: {code}")
        for i, char in enumerate(code):
            js = f"""
                (function() {{
                    var inputs = document.querySelectorAll('.otp-input');
                    var inp = inputs[{i}];
                    if (!inp) return;
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(inp, '{char}');
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }})();
            """
            sb.execute_script(js)
            time.sleep(0.1)

        print("✅ OTP已填入")
        time.sleep(0.5)

        print("🚀 点击验证...")
        verify_clicked = False
        for sel in [
            '//button[contains(., "Verify Code")]',
            '//span[contains(., "Verify Code")]',
            'button[type="submit"]',
        ]:
            try:
                if sb.is_element_visible(sel):
                    sb.click(sel)
                    verify_clicked = True
                    break
            except Exception:
                continue

        if not verify_clicked:
            print("❌ 验证按钮缺失")
            sb.save_screenshot("kerit_no_verify_btn.png")
            return

        print("⏳ 等待跳转...")
        for _ in range(80):
            try:
                url = sb.get_current_url()
                if "/session" in url:
                    print("✅ 登录成功！")
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            print("❌ 登录超时")
            sb.save_screenshot("kerit_login_timeout.png")
            return

        do_renew(sb)


if __name__ == "__main__":
    run_script()
