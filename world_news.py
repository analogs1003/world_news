import feedparser
import folium
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator

# ==========================================
# 1. 設定値
# ==========================================
MAX_ARTICLES = 20
SEARCH_PERIOD = "7d"
JST_OFFSET = 9
SHARED_TOPIC_MIN = 8

SCORE_NEW = 2.0
SCORE_OLD = 0.1
THRESH_RED = 12.0
THRESH_ORANGE = 6.0
THRESH_YELLOW = 3.0

COLORS = {
    "RED": "#ff1744", "ORANGE": "#ff9100", "YELLOW": "#ffea00", "CYAN": "#00e5ff",
    "BG_DARK": "#1e1e1e", "TEXT_SOFT": "#e0e0e0", "LINK_SAGE": "#a5d6a7", "BLUE_PALE": "#90caf9"
}

# REGIONS は変更なしのため省略（実際にはお手元のリストをそのままお使いください）
REGIONS = {
    # ...（中略：以前のコードのREGIONSリスト）...
    "韓国 🇰🇷": [35.90, 127.76, "KR", "ko", "일본"],
    "中国 🇨🇳": [34.66, 104.16, "CN", "zh-CN", "日本"],
    "台湾 🇹🇼": [23.69, 120.96, "TW", "zh-TW", "日本"],
    "香港 🇭🇰": [22.31, 114.16, "HK", "zh-TW", "日本"],
    "タイ 🇹🇭": [15.87, 100.99, "TH", "th", "ญี่ปุ่น"],
    "ベトナム 🇻🇳": [14.05, 108.27, "VN", "vi", "Nhật Bản"],
    "シンガポール 🇸🇬": [1.35, 103.81, "SG", "en", "Japan"],
    "マレーシア 🇲🇾": [4.21, 101.97, "MY", "en", "Japan"],
    "フィリピン 🇵🇭": [12.87, 121.77, "PH", "en", "Japan"],
    "インドネシア 🇮🇩": [-0.78, 113.92, "ID", "id", "Jepang"],
    "インド 🇮🇳": [20.59, 78.96, "IN", "en", "Japan"],
    "オーストラリア 🇦🇺": [-25.27, 133.77, "AU", "en", "Japan"],
    "NZ 🇳🇿": [-40.90, 174.88, "NZ", "en", "Japan"],
    "アメリカ 🇺🇸": [37.09, -95.71, "US", "en", "Japan"],
    "カナダ 🇨🇦": [56.13, -106.34, "CA", "en", "Japan"],
    "メキシコ 🇲🇽": [23.63, -102.55, "MX", "es", "Japón"],
    "ブラジル 🇧🇷": [-14.23, -51.92, "BR", "pt", "Japão"],
    "アルゼンチン 🇦🇷": [-38.41, -63.61, "AR", "es", "Japón"],
    "チリ 🇨🇱": [-35.67, -71.54, "CL", "es", "Japón"],
    "イギリス 🇬🇧": [55.37, -3.43, "GB", "en", "Japan"],
    "フランス 🇫🇷": [46.22, 2.21, "FR", "fr", "Japon"],
    "ドイツ 🇩🇪": [51.16, 10.45, "DE", "de", "Japan"],
    "イタリア 🇮🇹": [41.87, 12.56, "IT", "it", "Giappone"],
    "スペイン 🇪🇸": [40.46, -3.74, "ES", "es", "Japón"],
    "オランダ 🇳🇱": [52.13, 5.29, "NL", "nl", "Japan"],
    "スイス 🇨🇭": [46.81, 8.22, "CH", "de", "Japan"],
    "スウェーデン 🇸🇪": [60.12, 18.64, "SE", "sv", "Japan"],
    "ノルウェー 🇳🇴": [60.47, 8.46, "NO", "no", "Japan"],
    "フィンランド 🇫🇮": [61.92, 25.74, "FI", "fi", "Japani"],
    "デンマーク 🇩🇰": [56.26, 9.50, "DK", "da", "Japan"],
    "ポーランド 🇵🇱": [51.91, 19.14, "PL", "pl", "Japonia"],
    "ギリシャ 🇬🇷": [39.07, 21.82, "GR", "el", "Ιαπωνία"],
    "ロシア 🇷🇺": [61.52, 105.31, "RU", "ru", "Япония"],
    "トルコ 🇹🇷": [38.96, 35.24, "TR", "tr", "Japonya"],
    "イスラエル 🇮🇱": [31.04, 34.85, "IL", "he", "יפן"],
    "サウジアラビア 🇸🇦": [23.88, 45.07, "SA", "ar", "اليابان"],
    "UAE 🇦🇪": [23.42, 53.84, "AE", "en", "Japan"],
    "エジプト 🇪🇬": [26.82, 30.80, "EG", "ar", "اليابان"],
    "南アフリカ 🇿🇦": [-30.55, 22.93, "ZA", "en", "Japan"],
    "ナイジェリア 🇳🇬": [9.08, 8.67, "NG", "en", "Japan"],
    "モロッコ 🇲🇦": [31.79, -7.09, "MA", "fr", "Japon"],
}

# ==========================================
# 2. 補助関数
# ==========================================

def get_article_data(entry, current_time):
    pub_struct = getattr(entry, 'published_parsed', None)
    if pub_struct:
        utc_dt = datetime(*pub_struct[:6])
        jst_dt = utc_dt + timedelta(hours=JST_OFFSET)
        diff_hours = (current_time - time.mktime(pub_struct)) / 3600
        score = SCORE_NEW if diff_hours < 24 else SCORE_OLD
        return score, jst_dt.timestamp(), jst_dt.strftime('%m/%d %H:%M')
    return SCORE_OLD, 0, "時刻不明"

def build_country_panel_html(country, articles, total_score):
    """パネル内に表示するHTMLを生成"""
    count = len(articles)
    html = f"""
        <div style='border-bottom:1px solid #444; margin-bottom:15px; padding-bottom:10px;'>
            <b style='font-size:26px; color:{COLORS["BLUE_PALE"]};'>【{country}】</b><br>
            <span style='color:#888; font-size:16px;'>注目度: {total_score:.1f} / 記事数: {count}</span>
        </div>
    """
    for art in articles[:10]: # パネルなので少し多めに10件
        badge = f"<span style='background:#b71c1c; color:white; font-size:12px; padding:2px 6px; border-radius:3px; margin-right:8px;'>NEW</span>" if art["score"] > 1.0 else ""
        html += f"""
        <div style='margin-bottom:20px; border-bottom:1px solid #333; padding-bottom:10px;'>
            <div style='font-size:14px; color:#aaa; margin-bottom:4px;'>{art['time_str']}</div>
            <div style='display:flex; align-items:flex-start;'>
                {badge}
                <a href='{art['link']}' target='_blank' style='text-decoration:none; color:{COLORS["LINK_SAGE"]}; 
                   font-size:20px; font-weight:500;'>
                   {art['translated_title']}
                </a>
            </div>
        </div>
        """
    return html

def get_marker_color(total_score):
    """スコアに基づいてマーカーの色を返す"""
    if total_score >= THRESH_RED: return COLORS["RED"]
    if total_score >= THRESH_ORANGE: return COLORS["ORANGE"]
    if total_score >= THRESH_YELLOW: return COLORS["YELLOW"]
    return COLORS["CYAN"]

# ==========================================
# 3. メイン処理
# ==========================================

def fetch_and_process_country(country, info):
    lat, lon, gl, hl, query = info
    url = f"https://news.google.com/rss/search?q={query}+when:{SEARCH_PERIOD}&hl={hl}-{gl}&gl={gl}&ceid={gl}:{hl}"
    try:
        feed = feedparser.parse(url)
        articles = []
        now = time.time()
        for entry in feed.entries[:MAX_ARTICLES]:
            score, ts, t_str = get_article_data(entry, now)
            articles.append({
                "country": country, "lat": lat, "lon": lon, "link": entry.link,
                "raw_title": entry.title.split(" - ")[0].strip(),
                "score": score, "pub_time": ts, "time_str": t_str
            })
        if not articles: return []
        translator = GoogleTranslator(source='auto', target='ja')
        raw_titles = [a["raw_title"] for a in articles]
        # 簡易的な翻訳リトライ
        translated = []
        try:
            translated = translator.translate("\n".join(raw_titles)).split("\n")
        except:
            translated = raw_titles
        for i, art in enumerate(articles):
            art["translated_title"] = translated[i] if i < len(translated) else art["raw_title"]
        return articles
    except:
        return []

def create_global_news_center():
    print("🚀 データ収集中...")
    all_articles = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda p: fetch_and_process_country(*p), REGIONS.items()))
        for res in results: all_articles.extend(res)

    m = folium.Map(location=[20, 0], zoom_start=3, tiles="CartoDB dark_matter", world_copy_jump=True)

    # JavaScript関数の埋め込み (パネル制御用)
    # トレンド用と国別用の2つのパネルを制御できるようにします
    custom_js = """
    function openPanel(id, contentHTML) {
        if (contentHTML) {
            document.getElementById(id + '-content').innerHTML = contentHTML;
        }
        document.getElementById(id).style.display = 'block';
    }
    function closePanel(id) {
        document.getElementById(id).style.display = 'none';
    }

    // 地図オブジェクトが生成された後にイベントを仕込む
    // Foliumが作る地図変数名に合わせて自動実行されます
    window.addEventListener('DOMContentLoaded', function() {
        // 全てのleaflet地図オブジェクトに対して
        setTimeout(function() {
            var maps = [];
            // 地図インスタンスを探す（通常1つ）
            for (var key in window) {
                if (window[key] instanceof L.Map) {
                    var map = window[key];
                    map.on('popupopen', function(e) {
                        var container = e.popup._contentNode;
                        var trigger = container.querySelector('.news-data-trigger');
                        if (trigger) {
                            var html = trigger.querySelector('.payload').innerHTML;
                            openPanel('country-panel', html);
                            map.closePopup(); // 吹き出しを即座に閉じる
                        }
                    });
                }
            }
        }, 1000);
    });

    // 起動時にトレンドパネルを出す
    window.onload = function() {
        setTimeout(function() { openPanel('trend-panel'); }, 500);
    };
    """
    m.get_root().script.add_child(folium.Element(custom_js))
        
    # --- HTML要素（トレンドパネル ＆ 国別パネル） ---
    panel_styles = f"""
        position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); 
        width:90%; max-width:650px; background:rgba(20,20,20,0.98); color:white; 
        z-index:10000; padding:25px; border-radius:20px; border:2px solid #bb86fc; 
        overflow-y:auto; max-height:80vh; display:none; box-shadow:0 0 40px rgba(0,0,0,0.8);
        font-family: sans-serif;
    """

    common_html = f"""
    <div id="trend-panel" style="{panel_styles}">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h2 style="color:#bb86fc; margin:0;">🌍 世界の主要トレンド</h2>
            <button onclick="closePanel('trend-panel')" style="background:none; border:none; color:#aaa; font-size:40px; cursor:pointer;">&times;</button>
        </div>
        <ul id="trend-panel-content" style="list-style:none; padding:0;"></ul>
    </div>

    <div id="country-panel" style="{panel_styles} border-color:#90caf9;">
        <div style="display:flex; justify-content:flex-end;">
            <button onclick="closePanel('country-panel')" style="background:none; border:none; color:#aaa; font-size:40px; cursor:pointer;">&times;</button>
        </div>
        <div id="country-panel-content"></div>
    </div>

    <div style="position:fixed; top:80px; left:10px; z-index:9999;">
        <button onclick="openPanel('trend-panel')" style="background:#1f1f1f; color:#bb86fc; border:2px solid #bb86fc; width:60px; height:60px; border-radius:15px; cursor:pointer; font-size:30px;">🔥</button>
    </div>
    """
    m.get_root().html.add_child(folium.Element(common_html))

    # トレンド内容の作成
    topic_map = defaultdict(list)
    for a in all_articles: topic_map[a["translated_title"]].append(a)
    shared = {t: l for t, l in topic_map.items() if len(l) >= SHARED_TOPIC_MIN}
    shared_html = ""
    for title, links in sorted(shared.items(), key=lambda x: len(x[1]), reverse=True):
        tags = "".join([f"<a href='{l['link']}' target='_blank' style='display:inline-block; background:#333; color:#03dac6; padding:6px 12px; border-radius:8px; margin:5px 5px 0 0; text-decoration:none; font-size:14px; border:1px solid #03dac6;'>{l['country']}</a>" for l in links])
        shared_html += f"<li style='margin-bottom:25px; border-bottom:1px solid #444; padding-bottom:15px;'><div style='font-size:18px; font-weight:bold;'>{title} <span style='color:#bb86fc;'>({len(links)}カ国)</span></div><div style='display:flex; flex-wrap:wrap;'>{tags}</div></li>"
    
    # トレンドの中身をJSでセット
    m.get_root().script.add_child(folium.Element(f"document.getElementById('trend-panel-content').innerHTML = `{shared_html or '<li>トレンドなし</li>'}`;"))

    # マーカーの設置
    country_groups = defaultdict(list)
    for a in all_articles: country_groups[a["country"]].append(a)

    for country, articles in country_groups.items():
        total_score = sum(a["score"] for a in articles)
        articles.sort(key=lambda x: x['pub_time'], reverse=True)
        color = get_marker_color(total_score)
        
        # パネル用の中身を生成
        panel_content = build_country_panel_html(country, articles, total_score)
        # JSでエラーにならないよう、バッククォートと改行を安全に処理
        safe_content = panel_content.replace("`", "\\`").replace("\n", " ")

        # --- Popupの仕組みを「データ転送用」として使う ---
        # このHTML自体は表示される前にJSで横取りされます
        secret_data_html = f"""
        <div class="news-data-trigger" style="display:none;">
            <div class="payload">{safe_content}</div>
        </div>
        """

        folium.CircleMarker(
            location=[articles[0]["lat"], articles[0]["lon"]],
            radius=5 + (total_score * 2.5),
            tooltip=f"{country} (スコア: {total_score:.1f})",
            # 変数名を secret_data_html に合わせて修正しました
            popup=folium.Popup(secret_data_html), 
            color=color, fill=True, fill_color=color, fill_opacity=0.6, weight=1
        ).add_to(m)
    
    # 凡例
    legend_html = f'''<div style="position:fixed; bottom:30px; left:20px; width:130px; background:rgba(255,255,255,0.9); border:2px solid grey; z-index:9999; font-size:12px; padding:10px; border-radius:10px;">
        <b>注目度</b><br>
        <i style="background:{COLORS['RED']};width:10px;height:10px;display:inline-block"></i> 激アツ<br>
        <i style="background:{COLORS['ORANGE']};width:10px;height:10px;display:inline-block"></i> 活発<br>
        <i style="background:{COLORS['YELLOW']};width:10px;height:10px;display:inline-block"></i> 通常<br>
        <i style="background:{COLORS['CYAN']};width:10px;height:10px;display:inline-block"></i> 静か</div>'''
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save("index.html")
    print("✨ 完成しました！")

if __name__ == "__main__":
    create_global_news_center()