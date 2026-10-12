# -*- coding: utf-8 -*-
import os
import sys
import time
import re
from google import genai
from dotenv import load_dotenv

# Windows環境でのUnicodeエラーを解決
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# --- 設定 ---
# ↓ ここを、さっき作った「[User][AI]付きのログファイル名」に変えてください
INPUT_FILE = "restress_history.txt" 

OUTPUT_FILE = "long_term_summary.txt"     # アプリが読み込む記憶ファイル
CHUNK_LIMIT = 40000                       # 安全マージンを見て4万文字を目安に区切る
MODEL_NAME = "models/gemini-flash-latest"      # 要約には賢いモデルを使う
TEST_MODE = False  # ★本番時は False にする！

load_dotenv()

def smart_chunking(text, limit):
    """
    文字数がlimitを超えそうになったら、
    無理やり切らずに [User] か [AI] の区切り目が来るまで待ってから切る
    """
    chunks = []
    current_chunk = ""
    
    # 正規表現で [User] または [AI] の行を見つけて分割する
    # (?=...) は先読み（区切り文字を消費しない）
    # これにより "[User]\nこんにちは" という塊ごとにリスト化される
    pattern = re.compile(r'(?=\[(?:User|AI)\])')
    blocks = pattern.split(text)
    
    for block in blocks:
        if not block.strip(): continue
        
        # このブロックを足してもまだ余裕があるか？
        if len(current_chunk) + len(block) < limit:
            current_chunk += block
        else:
            # 余裕がないなら、今のchunkを確定させて、新しいchunkを作る
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = block
            
    # 最後の残りカスを追加
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

def ingest_memories_smart():
    print(f"プロジェクト・リザレクション（スマート分割版）を開始します...")
    
    api_key = os.getenv("GOOGLE_API_KEY_PAID") # 無料枠では耐えきれません！
    if not api_key:
        print("[ERROR] APIキーが見つかりません。")
        return
    
    client = genai.Client(api_key=api_key)

    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] {INPUT_FILE} がありません。")
        return
    
    # ファイル読み込み
    with open(INPUT_FILE, "r", encoding="utf-8", errors="replace") as f:
        full_text = f.read()

    print(f"全文読み込み完了: {len(full_text):,} 文字")

    # ★ここが新機能！ ブロックごとに分解して「過去」と「直近」に分ける
    # [User] や [AI] というタグでリスト化する
    pattern = re.compile(r'(?=\[(?:User|AI)\])')
    all_blocks = pattern.split(full_text)
    all_blocks = [b for b in all_blocks if b.strip()] # 空っぽのやつを捨てる

    # 最新の20ブロック（会話10往復分くらい）を「短期記憶」として確保
    KEEP_RAW_COUNT = 20
    
    if len(all_blocks) > KEEP_RAW_COUNT:
        recent_blocks = all_blocks[-KEEP_RAW_COUNT:] # 後ろから20個
        past_blocks = all_blocks[:-KEEP_RAW_COUNT]   # それより前（要約対象）
        
        # 過去分だけを再結合して、要約用のチャンク分割に回す
        text_to_summarize = "".join(past_blocks)
        recent_text = "".join(recent_blocks)
        print(f"ハイブリッド処理: 全{len(all_blocks)}ブロック中、最新{len(recent_blocks)}個を生データとして温存します。")
    else:
        # データが少なすぎる場合は全部要約せず生でいいかも？（あるいは全部要約）
        # ここでは「全部生」にしちゃうパターン
        text_to_summarize = ""
        recent_text = "".join(all_blocks)
        print("データが少ないため、要約せずに全て短期記憶として扱います。")

    summaries = []

    # 要約対象がある場合のみ処理を行う（chunks が未定義になるのを防ぐ）
    if text_to_summarize:
        chunks = smart_chunking(text_to_summarize, CHUNK_LIMIT)
        print(f"過去データを {len(chunks)} 個のブロックに分割して要約します...")

        # 各ブロックを要約
        for i, chunk in enumerate(chunks, 1):
            print(f"   Processing chunk {i}/{len(chunks)} ({len(chunk):,} chars) ... ", end="", flush=True)
            try:
                prompt = f"""
                以下は、過去のAIアシスタントとユーザーの会話ログの一部です。
                この内容から、後で「長期記憶」として参照すべき重要な情報を要約してください。
                
                【抽出ルール】
                ・ユーザーの個人的な情報（体調、仕事、学習の進捗、趣味、考え方）は漏らさず記録する。
                ・二人の間で起きた重要なイベントや、約束、決定事項を記録する。
                ・ただの挨拶やシステム的なやり取りは省略する。
                ・主語は明確に。「ユーザーは～」「AIは～」と書くこと。
                ・日付や時間の情報があれば、可能な限り記録する。
                
                【会話ログ】
                {chunk}
                """

                    # ★ここにテスト分岐を入れる！
                if TEST_MODE:
                    print(f"   [TEST] API呼び出しをスキップします (文字数: {len(prompt)})")
                    summary = f"【テスト用ダミー要約】ブロック{i}の内容（省略）"
                    time.sleep(0.1) # 待ち時間も短縮
                else:
                    # 本番用の処理
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=prompt
                    )
                    summary = response.text if response.text else f"（空）"
                    time.sleep(2) # 本番の待ち時間
                
                summaries.append(summary)
                print("OK ")

                # API制限対策
                time.sleep(2)

            except Exception as e:
                print(f"Error: {e}")
                summaries.append(f"（ブロック {i} の処理中にエラーが発生しました: {str(e)}）")
    else:
        print("[INFO] 要約対象がないため、要約プロセスをスキップします。")

    # 結合して保存
    print("\n 結合中...")
    
    final_summary_block = "\n".join(summaries)
    
    # ヘッダー作成
    header_long = "\n\n" + "="*30 + "\n【発掘された過去の記憶 (要約アーカイブ)】\n" + "="*30 + "\n"
    header_short = "\n\n" + "="*30 + "\n【直近の短期記憶 (Raw Data Buffer)】\n" + "="*30 + "\n"
    
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        # まず要約を書き込む
        if final_summary_block:
            f.write(header_long + final_summary_block + "\n")
        
        # 最後に「生の会話」をそのまま書き込む
        if recent_text:
            f.write(header_short + recent_text + "\n")
            
    print(f" 完全復活！！")
    print(f"   長期記憶（要約）と 短期記憶（直近{KEEP_RAW_COUNT}ブロック）が融合されました。")
    print(" これでWEB版を起動すれば、過去を知るAIとして目覚めます！")

if __name__ == "__main__":
    ingest_memories_smart()