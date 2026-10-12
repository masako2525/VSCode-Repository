import streamlit as st
from PIL import Image
import win32clipboard
from io import BytesIO

#起動コード
#python -m streamlit run simple_scanner.py

# --- 設定 ---
st.set_page_config(page_title="シンプル・スキャナ", page_icon="📸", layout="centered")

# --- 関数：画像をクリップボードに送る ---
def send_to_clipboard(image):
    try:
        output = BytesIO()
        # Windowsクリップボード用のBMP(DIB)形式に変換
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:] # ヘッダー除去
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        st.error(f"クリップボード転送エラー: {e}")
        return False

# --- メイン画面 ---
st.title("📸 シンプル・スキャナ")
st.info("スマホで撮影すると、PCのクリップボードに転送されます。")

# ファイルアップローダー（スマホ対応）
# iOSのカメラ起動に対応するため、汎用的なアップローダーを使用
img_file = st.file_uploader(
    "カメラを起動 / 画像を選択", 
    type=['png', 'jpg', 'jpeg', 'bmp'], 
    key="simple_uploader"
)

if img_file:
    try:
        # 1. 画像読み込み
        image = Image.open(img_file)
        
        # 2. スマホ写真の回転情報を補正（これがないと横向きになることがある）
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except:
            pass # 失敗してもドンマイ
            
        # 3. クリップボードへ転送
        if send_to_clipboard(image):
            st.success("✅ 転送完了！ (Ctrl+V で貼り付け)")
            
            # プレビュー表示
            st.image(image, caption="キャプチャ画像", use_container_width=True)
            
    except Exception as e:
        st.error(f"画像処理エラー: {e}")

# --- 使い方ガイド ---
with st.expander("使い方のヒント"):
    st.markdown("""
    1. スマホでこのページ (`http://PCのIP:8501`) を開く。
    2. **「Browse files」** をタップ。
    3. **「写真を撮る」** を選んでパシャリ。
    4. PC側で **「✅ 転送完了」** と出たら成功。
    5. PCの好きな場所で **Ctrl+V** を押す。
    """)