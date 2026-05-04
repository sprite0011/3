import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import os
import datetime


# --- 0. 外観のカスタマイズ（クリーン＆モダンUI） ---
st.markdown(
    """
    <style>
    /* 全体の背景：清潔感のある白に戻す */
    .stApp {
        background-color: #ffffff;
        color: #1e1e2f;
    }

    /* サイドバー：白基調で境界線のみ */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }

    /* タイトル：スタイリッシュなグラデーション */
    h1 {
        background: linear-gradient(to right, #4b6cb7, #182848);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        text-align: center;
        padding-bottom: 20px;
    }

    /* スコアカード：白背景に薄い影をつけて浮かせる */
    .stMetric {
        background: #ffffff;
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #f0f0f0;
    }

    /* 地図の枠：太めの白枠と影でスマホアプリ風に */
    .stFolium {
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        border: 2px solid #ffffff;
    }

    /* 【お気に入り】ボタンのデザイン：丸みとグラデーション */
    .stButton>button {
        border-radius: 25px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 25px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(118, 75, 162, 0.3);
    }
    
    /* ボタンにマウスを乗せた時の動き */
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(118, 75, 162, 0.5);
    }

    /* 入力欄のデザイン */
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 1. セッション状態（データ保持）の初期化
# ==========================================

# --- 1. セッション状態の初期化（ファイルから読み込む） ---
SAVE_FILE = "save_data.csv"

if 'point_owners' not in st.session_state:
    if os.path.exists(SAVE_FILE):
        try:
            # 保存ファイルからデータを読み込む
            df_save = pd.read_csv(SAVE_FILE)
            # spotをキーにして、teamとtimeを辞書形式で復元する
            st.session_state.point_owners = {
                row['spot']: {"team": row['team'], "time": row['time']} 
                for _, row in df_save.iterrows()
            }
        except:
            st.session_state.point_owners = {}
    else:
        st.session_state.point_owners = {}


if 'ward_owners' not in st.session_state:
    all_wards = [
        "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区", 
        "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", 
        "中野区", "杉並区", "豊島区", "北区", "荒川区", "板橋区", 
        "練馬区", "足立区", "葛飾区", "江戸川区"
    ]
    st.session_state.ward_owners = {name: "gray" for name in all_wards}

if 'selected_pin' not in st.session_state:
    st.session_state.selected_pin = None

if 'point_owners' not in st.session_state:
    st.session_state.point_owners = {}

# ==========================================
# 2. 関数定義（ロジックの部品作成）
# ==========================================

def load_geojson(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

@st.cache_data
def load_points():
    if os.path.exists("points.csv"):
        df = pd.read_csv("points.csv")
        df['ward'] = df['ward'].str.strip()
        df['name'] = df['name'].str.strip()
        return df
    return pd.DataFrame(columns=['ward', 'name', 'lat', 'lng'])

# --- 区の色を判定するコアロジック ---
def determine_ward_color(ward_name, df_points):
    ward_df = df_points[df_points['ward'] == ward_name]
    red_count = 0
    blue_count = 0
    
    for _, row in ward_df.iterrows():
        p_full_name = row['name']
        p_short_name = p_full_name.split(":")[-1].strip() if ":" in p_full_name else p_full_name
        
        data = st.session_state.point_owners.get(p_short_name)
        owner = data.get("team") if data else None # 辞書からteamを取り出す
        if owner == "red":
            red_count += 1
        elif owner == "blue":
            blue_count += 1
            
    if red_count == 0 and blue_count == 0:
        return "gray"
    elif red_count > blue_count:
        return "red"
    elif blue_count > red_count:
        return "blue"
    else:
        return "purple" # 同数は紫

# --- 全区の色をリフレッシュする ---
def refresh_all_ward_colors(df_points):
    for ward in st.session_state.ward_owners.keys():
        new_color = determine_ward_color(ward, df_points)
        st.session_state.ward_owners[ward] = new_color

# ==========================================
# 3. メイン処理（UIと地図の構築）
# ==========================================

st.title("⚔️ 東京23区 陣取りバトル")

# サイドバー設定
st.sidebar.header("🕹️ 操作パネル")
my_team = st.sidebar.radio("あなたのチーム", ["red", "blue"])
st.sidebar.info("ピンをクリック → 下のボタンで制圧！")

# データの読み込み
df_points = load_points()

# 【重要】描画の「直前」に全区の所有状況を再計算する
refresh_all_ward_colors(df_points)

# 地図の土台作成
m = folium.Map(location=[35.6895, 139.75], zoom_start=11)

# A. 各区の面（GeoJSON）を描画
wards_data = [
    {"file": "chiyoda.geojson", "label": "千代田区"}, {"file": "chuo.geojson", "label": "中央区"},
    {"file": "minato.geojson", "label": "港区"}, {"file": "shinjuku.geojson", "label": "新宿区"},
    {"file": "bunkyo.geojson", "label": "文京区"}, {"file": "taito.geojson", "label": "台東区"},
    {"file": "sumida.geojson", "label": "墨田区"}, {"file": "koto.geojson", "label": "江東区"},
    {"file": "shinagawa.geojson", "label": "品川区"}, {"file": "meguro.geojson", "label": "目黒区"},
    {"file": "ota.geojson", "label": "大田区"}, {"file": "setagaya.geojson", "label": "世田谷区"},
    {"file": "shibuya.geojson", "label": "渋谷区"}, {"file": "nakano.geojson", "label": "中野区"},
    {"file": "suginami.geojson", "label": "杉並区"}, {"file": "toshima.geojson", "label": "豊島区"},
    {"file": "kita.geojson", "label": "北区"}, {"file": "arakawa.geojson", "label": "荒川区"},
    {"file": "itabashi.geojson", "label": "板橋区"}, {"file": "nerima.geojson", "label": "練馬区"},
    {"file": "adachi.geojson", "label": "足立区"}, {"file": "katsushika.geojson", "label": "葛飾区"},
    {"file": "edogawa.geojson", "label": "江戸川区"}
]

for w_info in wards_data:
    geojson_data = load_geojson(w_info["file"])
    if geojson_data:
        current_color = st.session_state.ward_owners.get(w_info["label"], "gray")
        folium.GeoJson(
            geojson_data,
            style_function=lambda x, color=current_color: {
                'fillColor': color,
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.4,
            },
            tooltip=w_info["label"]
        ).add_to(m)

# B. 各ピンの描画
for _, row in df_points.iterrows():
    p_full_name = row['name']
    p_short_name = p_full_name.split(":")[-1].strip() if ":" in p_full_name else p_full_name
    
    # ピン個別の所有チームを取得
    data = st.session_state.point_owners.get(p_short_name)
    team = data.get("team") if data else None
    
    # チームに応じた色（未占領はblack）
    icon_color = "black" 
    if team == "red": icon_color = "red"
    elif team == "blue": icon_color = "blue"
    
    folium.Marker(
        location=[row['lat'], row['lng']],
        popup=p_full_name,
        icon=folium.Icon(color=icon_color, icon="info-sign")
    ).add_to(m)

# ==========================================
# 4. 地図の表示とクリックイベントの処理
# ==========================================

output = st_folium(m, width="100%", height=600, key="map")

# ピンをクリックした情報を取得
if output.get("last_object_clicked_popup"):
    st.session_state.selected_pin = output["last_object_clicked_popup"]

# --- チェックイン操作UI ---
# --- 6. チェックイン・取り消しボタンの処理 ---
if st.session_state.selected_pin:
    # 判定用に文字を分割
    raw_text = st.session_state.selected_pin.replace("：", ":")
    parts = raw_text.split(":")
    clicked_spot = parts[-1].strip()

    st.write("---")
    st.subheader(f"📍 選択中: {clicked_spot}")
    
    # 現在このスポットを占領しているチームを確認
    data = st.session_state.point_owners.get(clicked_spot)
    current_p_owner = data.get("team") if data else None
    
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        # すでに誰かが占領しているかチェック
        if current_p_owner:
            # 占領済みの場合、チェックインボタンの代わりにメッセージを表示
            owner_label = "🔴 赤チーム" if current_p_owner == "red" else "🔵 青チーム"
            st.error(f"この地点はすでに {owner_label} が占領しています。")
        else:
            # まだ誰も占領していない場合のみ、チェックインボタンを表示
           if st.button(f"🚩 チェックイン", use_container_width=True):
            now_str = datetime.datetime.now().strftime('%m/%d %H:%M:%S')
            st.session_state.point_owners[clicked_spot] = {"team": my_team, "time": now_str}
            
            # 【A】現在のピン状況を保存 (save_data.csv)
            save_list = [{"spot": k, "team": v["team"], "time": v["time"]} for k, v in st.session_state.point_owners.items()]
            pd.DataFrame(save_list).to_csv(SAVE_FILE, index=False, encoding="utf-8")
            
            # 【B】全履歴（バックアップ）を追記保存 (all_history.csv)
            LOG_FILE = "all_history.csv"
            new_log = pd.DataFrame([{"spot": clicked_spot, "team": my_team, "time": now_str}])
            
            # ファイルがなければ作成、あればヘッダーなしで追記
            if not os.path.exists(LOG_FILE):
                new_log.to_csv(LOG_FILE, index=False, encoding="utf-8")
            else:
                new_log.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8")
            
            st.success(f"{clicked_spot} を制圧！")
            st.rerun()

    with col_btn2:
        # 解除機能はパスワード付きで残しておく（管理用）
        if current_p_owner:
            if f"confirm_cancel_{clicked_spot}" not in st.session_state:
                st.session_state[f"confirm_cancel_{clicked_spot}"] = False

            if not st.session_state[f"confirm_cancel_{clicked_spot}"]:
                if st.button(f"⚪ 占領を解除", use_container_width=True):
                    st.session_state[f"confirm_cancel_{clicked_spot}"] = True
                    st.rerun()
            else:
                cancel_pw = st.text_input("解除パスワードを入力", type="password", key=f"pw_{clicked_spot}")
                if cancel_pw == "987654321": # 管理者メニューと同じパスワード
                    if st.button("✅ 実行", use_container_width=True):
                        if clicked_spot in st.session_state.point_owners:
                            del st.session_state.point_owners[clicked_spot]
                        new_save_df = pd.DataFrame([{"spot": k, "team": v} for k, v in st.session_state.point_owners.items()])
                        new_save_df.to_csv(SAVE_FILE, index=False, encoding="utf-8")
                        st.session_state[f"confirm_cancel_{clicked_spot}"] = False
                        st.warning(f"{clicked_spot} の占領を解除しました。")
                        st.session_state.selected_pin = None
                        st.rerun()
        else:
            if st.button("閉じる", use_container_width=True):
                st.session_state.selected_pin = None
                st.rerun()

    # (オプション) 下に小さくキャンセルボタンを置く場合
    if current_p_owner:
        if st.button("閉じる"):
            st.session_state.selected_pin = None
            st.rerun()



# --- 7. 管理者用データ初期化機能 ---
st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ 管理者メニュー")
admin_password = st.sidebar.text_input("管理用パスワード", type="password")

if admin_password == "9876543210":
    if st.sidebar.button("⚠️ 盤面をリセットする", help="占領状況を初期化しますが、ログは残ります"):
        # セッション上のピン情報をクリア
        st.session_state.point_owners = {}
        
        # 現在のピン保存ファイル(save_data.csv)だけを空にする
        df_reset = pd.DataFrame(columns=['spot', 'team', 'time'])
        df_reset.to_csv(SAVE_FILE, index=False, encoding="utf-8")
        
        st.sidebar.success("盤面をリセットしました（履歴は保存されています）。")
        st.rerun()


# --- 7.5 ログ表示の認証・切り替えロジック ---
st.sidebar.markdown("---")

# 認証状態を管理するフラグの初期化
if "log_authenticated" not in st.session_state:
    st.session_state.log_authenticated = False

# まだ認証されていない場合、パスワード入力を求める
if not st.session_state.log_authenticated:
    log_password = st.sidebar.text_input("ログ閲覧パスワード", type="password", key="log_auth_pw")
    if log_password == "123":
        st.session_state.log_authenticated = True
        st.rerun()
    elif log_password != "":
        st.sidebar.error("パスワードが違います")
else:
    # 認証済みの場合は、表示・非表示を切り替えるボタンを出す
    # セッション状態で表示ON/OFFを管理
    if "show_log_flag" not in st.session_state:
        st.session_state.show_log_flag = False

    if st.sidebar.button("アクティビティログを表示/隠す"):
        st.session_state.show_log_flag = not st.session_state.show_log_flag
        st.rerun()
    
    # 認証を解除してロックするボタン（念のため）
    if st.sidebar.button("ログをロックする"):
        st.session_state.log_authenticated = False
        st.session_state.show_log_flag = False
        st.rerun()

# --- 8. スコアボードの表示 ---
# 各チームが占領している区の数をカウント
ward_counts = list(st.session_state.ward_owners.values())
red_wards = ward_counts.count("red")
blue_wards = ward_counts.count("blue")
purple_wards = ward_counts.count("purple") # 同数の区

# メイン画面にスコアを表示
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🔴 赤チーム", f"{red_wards} 区")
with col2:
    st.metric("🔵 青チーム", f"{blue_wards} 区")
with col3:
    st.metric("🟣 競合中", f"{purple_wards} 区")

st.markdown("---")

# --- 9. 占領履歴の表示 ---
if st.session_state.get("log_authenticated") and st.session_state.get("show_log_flag"):
    st.write("## 📜 歴代のアクティビティログ（全記録）")
    LOG_FILE = "all_history.csv"
    
    if os.path.exists(LOG_FILE):
        # バックアップファイルを読み込む
        df_log = pd.read_csv(LOG_FILE)
        
        # 表示用に加工
        df_log["チーム"] = df_log["team"].apply(lambda x: "🔴 赤チーム" if x == "red" else "🔵 青チーム")
        display_df = df_log[["time", "チーム", "spot"]].rename(columns={"time": "時間", "spot": "場所"})
        
        # 最新が上に来るように逆順で表示
        st.dataframe(display_df.iloc[::-1], use_container_width=True, height="content")
    else:
        st.info("バックアップ履歴はまだありません。")