import subprocess
import os
import sys
import signal

# ——— LẤY THƯ MỤC CHỨA SCRIPT LÀM GỐC ———
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ——— ĐƯỜNG DẪN TƯƠNG ĐỐI: thư mục “internet” nằm cùng cấp với file script ———
INTERNET_DIR = os.path.join(BASE_DIR, "internet")
ADB_PATH = os.path.join(INTERNET_DIR, "platform-tools-latest-windows", "platform-tools", "adb.exe")
GNIREHTET_DIR = os.path.join(INTERNET_DIR, "gnirehtet-rust-win64-v2.5.1", "gnirehtet-rust-win64")
GNIREHTET_EXE = os.path.join(GNIREHTET_DIR, "gnirehtet.exe")
GNIREHTET_APK = os.path.join(GNIREHTET_DIR, "gnirehtet.apk")

def run(cmd, cwd=None, env=None):
    """
    Chạy cmd, capture và in stdout + stderr để debug.
    Trả về exit code.
    """
    try:
        p = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = p.communicate()
        if out:
            print(out.strip())
        if err:
            print("⚠️ STDERR:", err.strip())
        return p.returncode
    except FileNotFoundError:
        print(f"❌ Không tìm thấy: {cmd[0]}")
        sys.exit(1)

def main():
    # Thiết lập env để gnirehtet dùng ADB của chúng ta
    env = os.environ.copy()
    env["ADB"] = ADB_PATH

    print("🔍 1. Kiểm tra thiết bị ADB…")
    if run([ADB_PATH, "devices"], env=env) != 0:
        print("→ Lỗi kết nối ADB. Hãy kiểm tra:\n"
              "   • USB Debugging đã bật trên điện thoại\n"
              "   • Driver ADB trên Windows đã cài đúng\n"
              "   • Khi cắm cáp sẽ hiện popup “Allow USB debugging?”, chọn Always allow")
        return

    print("🧹 2. Xóa các reverse port mappings cũ…")
    run([ADB_PATH, "reverse", "--remove-all"], env=env)

    print("📋 3. Thiết lập reverse port cho gnirehtet (31416)…")
    if run([ADB_PATH, "reverse", "tcp:31416", "tcp:31416"], env=env) != 0:
        print("→ Không thể tạo reverse tcp:31416. Kiểm tra Firewall Windows, hoặc chạy lại với quyền Administrator.")
        return

    print("📋 4. Danh sách reverse hiện tại:")
    run([ADB_PATH, "reverse", "--list"], env=env)

    print("📥 5. Cài/update gnirehtet client lên thiết bị…")
    if run([ADB_PATH, "install", "-r", GNIREHTET_APK], env=env) != 0:
        print("→ Lỗi khi cài gnirehtet.apk. Hãy kiểm tra file APK có đúng và tương thích.")
        return

    print("🔔 6. Trên điện thoại: khi GNIREHTET khởi động sẽ hiện yêu cầu VPN permission, bạn phải nhấn CHO PHÉP.")
    print("   Nếu không thấy popup, vào Cài đặt → Ứng dụng → gnirehtet → Cấp quyền VPN thủ công.")

    print("🚀 7. Khởi động reverse tethering (DNS Google)…")
    tether = subprocess.Popen(
        [GNIREHTET_EXE, "run", "-d", "8.8.8.8,8.8.4.4"],
        cwd=GNIREHTET_DIR,
        env=env
    )

    def handle_sigint(signum, frame):
        print("\n⏹️  Đang dừng reverse tethering…")
        tether.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    tether.wait()

if __name__ == "__main__":
    main()
