import feedparser
import folium
import webbrowser
import time
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator

# --- 1. 国の設定（REGIONS） ---
# 手元で自由にコメントアウト（行の頭に # を入れる）して調整してください
REGIONS = {
    # アジア・オセアニア
#    "日本 🇯🇵": [35.68, 139.76, "JP", "ja", "ニュース"],
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

    # 北米・中南米
    "アメリカ 🇺🇸": [37.09, -95.71, "US", "en", "Japan"],
    "カナダ 🇨🇦": [56.13, -106.34, "CA", "en", "Japan"],
    "メキシコ 🇲🇽": [23.63, -102.55, "MX", "es", "Japón"],
    "ブラジル 🇧🇷": [-14.23, -51.92, "BR", "pt", "Japão"],
    "アルゼンチン 🇦🇷": [-38.41, -63.61, "AR", "es", "Japón"],
    "チリ 🇨🇱": [-35.67, -71.54, "CL", "es", "Japón"],

    # ヨーロッパ
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

    # 中東・アフリカ
    "トルコ 🇹🇷": [38.96, 35.24, "TR", "tr", "Japonya"],
    "イスラエル 🇮🇱": [31.04, 34.85, "IL", "he", "יפן"],
    "サウジアラビア 🇸🇦": [23.88, 45.07, "SA", "ar", "اليابان"],
    "UAE 🇦🇪": [23.42, 53.84, "AE", "en", "Japan"],
    "エジプト 🇪🇬": [26.82, 30.80, "EG", "ar", "اليابان"],
    "南アフリカ 🇿🇦": [-30.55, 22.93, "ZA", "en", "Japan"],
    "ナイジェリア 🇳🇬": [9.08, 8.67, "NG", "en", "Japan"],
    "モロッコ 🇲🇦": [31.79, -7.09, "MA", "fr", "Japon"],
}

def safe_translate(translator, text_list):
    """翻訳失敗時にリトライする関数"""
    if not text_list: return []
    text = "\n".join(text_list)
    for i in range(3):
        try:
            result = translator.translate(text)
            return result.split("\n")
        except:
            time.sleep((i + 1) * 2)
    return text_list

def fetch_and_process_country(country, info):
    """各国からニュースを取得して翻訳する"""
    lat, lon, gl, hl, query = info
    url = f"https://news.google.com/rss/search?q={query}+when:24h&hl={hl}-{gl}&gl={gl}&ceid={gl}:{hl}"
    try:
        feed = feedparser.parse(url)
        raw_titles, articles = [], []
        for entry in feed.entries[:3]:
            title = entry.title.split(" - ")[0].strip()
            raw_titles.append(title)
            articles.append({"country": country, "lat": lat, "lon": lon, "link": entry.link})
        
        if not articles: return []
        
        translator = GoogleTranslator(source='auto', target='ja')
        translated = safe_translate(translator, raw_titles)
        
        for i, art in enumerate(articles):
            art["translated_title"] = translated[i] if i < len(translated) else raw_titles[i]
        return articles
    except:
        return []

def create_global_news_center():
    print(f"🚀 {len(REGIONS)}カ国のスキャンを開始します...")
    all_articles = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda p: fetch_and_process_country(*p), REGIONS.items()))
        for res in results:
            all_articles.extend(res)

    topic_links = defaultdict(list)
    for a in all_articles:
        topic_links[a["translated_title"]].append({"country": a["country"], "link": a["link"]})
    
    # 【3カ国以上】で話題のニュースを抽出
    shared_topics = {t: l for t, l in topic_links.items() if len(l) >= 3}

    m = folium.Map(location=[20, 0], zoom_start=2.3, tiles="CartoDB dark_matter", world_copy_jump=True)

    # --- パネルHTML生成 (国旗なし・テキストのみのボタン) ---
    shared_list_html = ""
    if shared_topics:
        sorted_topics = sorted(shared_topics.items(), key=lambda x: len(x[1]), reverse=True)
        for title, links in sorted_topics:
            # 国名テキストのみのタグを生成
            tags = "".join([f"<a href='{l['link']}' target='_blank' style='display:inline-block; background:#333; color:#03dac6; padding:6px 12px; border-radius:8px; margin:5px 5px 0 0; text-decoration:none; font-size:14px; border:1px solid #03dac6;'>{l['country']}</a>" for l in links])
            shared_list_html += f"""
            <li style='margin-bottom:30px; border-bottom:1px solid #444; padding-bottom:18px;'>
                <div style='font-size:19px; font-weight:bold; color:#fff; margin-bottom:12px; line-height:1.4;'>{title} <span style='color:#bb86fc;'>({len(links)}カ国)</span></div>
                <div style='display: flex; flex-wrap: wrap;'>{tags}</div>
            </li>"""
    else:
        shared_list_html = "<li style='font-size:16px;'>3カ国以上で話題のニュースは見つかりませんでした。</li>"

    panel_html = f"""
    <div id="news-panel" style="position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); width:90%; max-width:700px; background:rgba(20,20,20,0.98); color:white; z-index:10000; padding:30px; border-radius:20px; box-shadow:0 0 50px rgba(0,0,0,0.9); border:2px solid #bb86fc; font-family:sans-serif; overflow-y:auto; max-height:85vh; display:block;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:25px;">
            <h2 style="margin:0; color:#bb86fc; font-size:26px;">🌍 世界の主要トレンド (3カ国以上)</h2>
            <button onclick="document.getElementById('news-panel').style.display='none'" style="background:none; border:none; color:#aaa; font-size:40px; cursor:pointer;">&times;</button>
        </div>
        <ul style="padding-left:0; list-style:none;">{shared_list_html}</ul>
        <div style="text-align:center; margin-top:20px;"><button onclick="document.getElementById('news-panel').style.display='none'" style="background:#bb86fc; color:black; border:none; padding:15px 45px; border-radius:10px; cursor:pointer; font-weight:bold; font-size:20px;">地図を探索する</button></div>
    </div>
    <div id="show-button" style="position:fixed; top:80px; left:10px; z-index:9999;"><button onclick="document.getElementById('news-panel').style.display='block'" style="background:#1f1f1f; color:#bb86fc; border:2px solid #bb86fc; width:65px; height:65px; border-radius:15px; cursor:pointer; font-size:35px;">🔥</button></div>
    """
    m.get_root().html.add_child(folium.Element(panel_html))

    # 地図上のマーカー設置
    country_groups = defaultdict(list)
    for a in all_articles: country_groups[a["country"]].append(a)
    
    for country, articles in country_groups.items():
        pop_html = f"<div style='min-width:280px; font-family:sans-serif; padding:5px;'><b style='font-size:20px; border-bottom:3px solid #03dac6; padding-bottom:3px;'>【{country}】</b><br><br>"
        for art in articles:
            pop_html += f"<div style='margin-bottom:15px; line-height:1.5;'><a href='{art['link']}' target='_blank' style='text-decoration:none; color:#0056b3; font-size:16px; font-weight:bold;'>・{art['translated_title']}</a></div>"
        
        folium.CircleMarker(
            location=[articles[0]["lat"], articles[0]["lon"]],
            radius=13,
            popup=folium.Popup(pop_html + "</div>", max_width=450),
            tooltip=country,
            color="#03dac6",
            fill=True,
            fill_color="#03dac6",
            fill_opacity=0.7
        ).add_to(m)

    output_file = "index.html"
    m.save(output_file)

if __name__ == "__main__":
    create_global_news_center()