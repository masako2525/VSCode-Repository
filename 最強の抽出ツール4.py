import json
import os
import re

# --- 設定 ---
INPUT_FILE = "old_log.txt"           
OUTPUT_FILE = "restress_history.txt" 

def contains_japanese(text):
    return re.search(r'[ぁ-んァ-ン一-龥]', text) is not None

def is_garbage_or_thought(text, data_obj):
    """
    ゴミデータや「思考プロセス」を判定するフィルター (V7強化版)
    """
    if isinstance(data_obj, dict):
        # 1. 旧仕様: "thought": true
        if data_obj.get("thought") is True:
            return True
        
        # 2. ★新仕様: "isThought": true (今回見つけた犯人！)
        if data_obj.get("isThought") is True:
            return True

    # 3. テキスト自体にJSONの断片（ゴミ）が混ざっていないか？
    if '"thought": true' in text or '"isThought": true' in text:
        return True
    
    if '}] }, {' in text:
        return True

    return False

def extract_from_json_v7():
    print(f"🌍 '{INPUT_FILE}' を解析します (V7: isThought対応)...")
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ エラー: {INPUT_FILE} が見つかりません。")
        return

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        target_list = []

        # --- 構造探索 (V6と同じ) ---
        if isinstance(data, list):
            target_list = data
        elif isinstance(data, dict):
            keys_to_check = ["contents", "history", "messages", "parts"]
            for key in keys_to_check:
                if key in data and isinstance(data[key], list):
                    target_list = data[key]
                    break
            
            if not target_list and "chunkedPrompt" in data:
                print("   🕵️ 'chunkedPrompt' モードで解析...")
                chunked = data["chunkedPrompt"]
                if isinstance(chunked, list):
                    target_list = chunked
                elif isinstance(chunked, dict):
                    if "contents" in chunked:
                        target_list = chunked["contents"]
                    else:
                        for k, v in chunked.items():
                            if isinstance(v, list):
                                target_list = v
                                break

        if not target_list:
            print("❌ 解析不能")
            return

        # --- 抽出ロジック ---
        extracted_blocks = []
        garbage_count = 0
        thought_count = 0
        
        for turn in target_list:
            if not isinstance(turn, dict): continue

            # ★フィルター発動
            if is_garbage_or_thought("", turn):
                thought_count += 1
                continue

            role = turn.get("role", "unknown")
            text_content = ""
            
            # parts対応
            if "parts" in turn:
                if isinstance(turn["parts"], list):
                    for part in turn["parts"]:
                        if isinstance(part, dict):
                            # ★パーツ単位フィルター
                            if is_garbage_or_thought("", part):
                                thought_count += 1
                                continue
                            if "text" in part:
                                text_content += part["text"]
                        elif isinstance(part, str):
                            text_content += part
                elif isinstance(turn["parts"], str):
                     text_content = turn["parts"]
            elif "text" in turn:
                text_content = turn["text"]

            # ★テキスト内容フィルター
            if is_garbage_or_thought(text_content, {}):
                thought_count += 1
                continue

            if not text_content or not contains_japanese(text_content):
                garbage_count += 1
                continue

            label = "[User]" if role == "user" else "[AI]"
            block = f"{label}\n{text_content}"
            extracted_blocks.append(block)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n\n".join(extracted_blocks))
            
        print("-" * 30)
        print(f"✨ V7抽出完了！")
        print(f"   抽出数: {len(extracted_blocks)}")
        print(f"   思考プロセス除去: {thought_count} 件")
        print(f"   その他除外(日本語なし等): {garbage_count} 件")
        print(f"💾 '{OUTPUT_FILE}' 生成完了。")

    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    extract_from_json_v7()