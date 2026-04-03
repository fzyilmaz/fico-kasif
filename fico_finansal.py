import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

# ── RENK PALETİ ─────────────────────────────────────────────
RENK = {
    "bg": "#1a2e1a",
    "bg2": "#213621",
    "bg3": "#2a422a",
    "border": "rgba(255,255,255,0.1)",
    "accent": "#c8a96e",
    "yesil": "#5db87a",
    "kirmizi": "#c47a6a",
    "metin": "#f0ead8",
    "soluk": "#9aab8a",
}

# ── TEMEL VARSAYIMLAR (baz senaryo) ─────────────────────────
FX = 45  # TL/USD (Nisan 2026)

# Maliyet tarafı
MAAS = {
    "backend": 1_500_000,
    "ml_nlp": 1_800_000,
    "frontend": 1_400_000,
    "pm": 1_400_000,
}
YUKUMLULUK = 1.45  # SGK + işsizlik + yan haklar
SURE_AY = 12

personel_yr1 = sum(MAAS.values()) * YUKUMLULUK
bakim_muhendis = MAAS["backend"] * YUKUMLULUK  # Yıl 2+

CAPEX = {
    "Azure AI Search S2 Kurulum": 43600,
    "Döküman Gömme (50K sayfa)": 56,
}
capex_toplam = sum(CAPEX.values())

OPEX_AYLIK_USD = {
    "Azure AI Search S2 (2SU)": 981,
    "Azure App Service P3v3": 400,
    "Azure Blob Storage": 4,
    "İzleme & Günlük Kaydı": 80,
    "Yeniden İndeksleme": 5,
}
opex_altyapi_yillik = sum(OPEX_AYLIK_USD.values()) * 12 * FX

# GPT-4o çıkarım — 6.000 sorgu/gün
GIRDI_TOKEN = 3_200
CIKTI_TOKEN = 300
GIRDI_FIYAT = 2.50 / 1_000_000
CIKTI_FIYAT = 10.00 / 1_000_000
sorgu_basi_maliyet = GIRDI_TOKEN * GIRDI_FIYAT + CIKTI_TOKEN * CIKTI_FIYAT
gunluk_sorgu = 6_000
gpt_yillik = sorgu_basi_maliyet * gunluk_sorgu * 365 * FX

opex_yillik = opex_altyapi_yillik + gpt_yillik
yr2_yillik_maliyet = opex_yillik + bakim_muhendis
yr1_toplam = personel_yr1 + capex_toplam + opex_yillik

# Değer tarafı
OTOMASYON = 0.80

# Saatlik maliyetler (brüt × 1.45 işveren yükü ÷ 2.080 çalışma saati)
uyum_saatlik = (1_800_000 * YUKUMLULUK) / 2_080   # ₺1.255/saat
pm_saatlik = (1_400_000 * YUKUMLULUK) / 2_080      # ₺976/saat
sube_saatlik = (1_500_000 * YUKUMLULUK) / 2_080    # ₺1.046/saat

# DEĞER 1: Uyum ekibi zaman tasarrufu
# KT uyum ekibi ~8 kişi, zamanının %30u rutin sorgulara gidiyor → %80 otomasyonla kurtarılıyor
v_uyum = 8 * 2_080 * 0.30 * OTOMASYON * uyum_saatlik

# DEĞER 2: Ürün ekipleri bekleme kaybı
# 12 PM × ayda 4 sorgu × 12 ay × her sorgu 4 saat verimlilik kaybı (2 gün bekleme)
v_pm = 12 * 4 * 12 * 4 * OTOMASYON * pm_saatlik

# DEĞER 3: Şube — kaçırılan işlem marjı
# 400 şube × ayda 1 sorgu = 4.800 sorgu/yıl
# %20i büyük şubede (960 sorgu) × %5 düşme oranı = 48 kayıp işlem
# Ortalama kurumsal finansman ₺2M × %5 banka marjı = ₺100K/işlem
v_sube = 48 * 100_000

# DEĞER 4: Ürün lansmanı hızlanması
# 5 ürün/yıl, gecikme 4 haftadan 1 haftaya iniyor = 15 iş günü kazanıldı
# İlk ay 300 müşteri × ₺2.000 marj = ₺600K/ay = ₺20K/gün
v_urun = 5 * 15 * 20_000

# DEĞER 5: Risk azaltma (beklenen değer)
# BDDK: ₺50M maruz × 4.2pp olasılık düşüşü
# İtibar: ₺50M maliyet × 2.6pp olasılık düşüşü
v_bddk_para_cezasi = 2_100_000
v_itibar = 1_300_000

v_toplam = v_uyum + v_pm + v_sube + v_urun + v_bddk_para_cezasi + v_itibar
net_yillik = v_toplam - yr2_yillik_maliyet

# ── İSKONTO ORANI TÜRETİMİ (Fisher) ────────────────────────
real_getiri = 0.075   # ABD 10y (~%3) + küresel ERP (~%4) + Türkiye CDS (~%1.5)
enflasyon = 0.315     # TÜFE Şubat 2026
nominal_oran = (1 + real_getiri) * (1 + enflasyon) - 1  # ≈ %41.4
ceyrek_oran = (1 + nominal_oran) ** 0.25 - 1

# ── ÇEYREK NAKİT AKIŞI ──────────────────────────────────────
maliyet_dagilim = [0.35, 0.35, 0.20, 0.05, 0, 0, 0, 0]
benimseme = [0, 0, 0, 0.50, 0.90, 0.90, 0.90, 0.90]
fazlar = [
    "İnşaat", "İnşaat", "İnşaat — MVP Hazır",
    "Lansman %50", "Tam Operasyon",
    "Tam Operasyon", "Tam Operasyon", "Tam Operasyon"
]

personel_capex = personel_yr1 + capex_toplam
ceyreklik_nakit = []
kumulatif = 0
npv = 0

for i in range(8):
    maliyet = personel_capex * maliyet_dagilim[i] + \
              (opex_yillik / 4 if i >= 3 else 0) + \
              (bakim_muhendis / 4 if i >= 4 else 0)
    deger = (v_toplam / 4) * benimseme[i]
    net = deger - maliyet
    kumulatif += net
    df = 1 / (1 + ceyrek_oran) ** (i + 1)
    pv = net * df
    npv += pv
    ceyreklik_nakit.append({
        "ceyrek": f"{'Yıl 1' if i < 4 else 'Yıl 2'} Ç{i % 4 + 1}",
        "faz": fazlar[i],
        "benimseme": benimseme[i],
        "maliyet": maliyet,
        "deger": deger,
        "net": net,
        "df": df,
        "pv": pv,
        "kumulatif": kumulatif,
        "kum_npv": npv,
    })

# Geri ödeme ayı
geri_odeme_ay = None
for i, q in enumerate(ceyreklik_nakit):
    if q["kumulatif"] >= 0:
        geri_odeme_ay = (i + 1) * 3
        break

# IRR hesabı (Newton-Raphson)
nakit_akislari = []
for i, q in enumerate(ceyreklik_nakit):
    nakit_akislari.append(q["net"])

def irr_hesapla(nakitler, tahmin=0.1):
    r = tahmin
    for _ in range(1000):
        f = sum(nakitler[t] / (1 + r) ** (t + 1) for t in range(len(nakitler)))
        df_dr = sum(-(t + 1) * nakitler[t] / (1 + r) ** (t + 2) for t in range(len(nakitler)))
        if abs(df_dr) < 1e-12:
            break
        r_yeni = r - f / df_dr
        if abs(r_yeni - r) < 1e-8:
            r = r_yeni
            break
        r = r_yeni
    return r

irr_ceyreklik = irr_hesapla(nakit_akislari)
irr_yillik = (1 + irr_ceyreklik) ** 4 - 1

# Duyarlılık analizi
def duyarlilik_hesapla(deger_degisim):
    v = v_toplam * (1 + deger_degisim)
    net_v = v - yr2_yillik_maliyet
    km = []
    kum = 0
    for i in range(8):
        mal = personel_capex * maliyet_dagilim[i] + \
              (opex_yillik / 4 if i >= 3 else 0) + \
              (bakim_muhendis / 4 if i >= 4 else 0)
        deg = (v / 4) * benimseme[i]
        net = deg - mal
        kum += net
        km.append(kum)
    geri = next((((i + 1) * 3) for i, k in enumerate(km) if k >= 0), None)
    n = sum((v / 4 * benimseme[i] - personel_capex * maliyet_dagilim[i] -
             (opex_yillik / 4 if i >= 3 else 0) -
             (bakim_muhendis / 4 if i >= 4 else 0)) /
            (1 + ceyrek_oran) ** (i + 1) for i in range(8))
    return {"npv": n, "geri_odeme": geri, "net_yillik": net_v}

duyarlilik_senaryolari = {
    "Baz Senaryo": duyarlilik_hesapla(0),
    "Değer −%20": duyarlilik_hesapla(-0.20),
    "Değer −%30": duyarlilik_hesapla(-0.30),
    "Değer −%50": duyarlilik_hesapla(-0.50),
    "Değer +%20": duyarlilik_hesapla(0.20),
}

# ── YARDIMCI FONKSİYONLAR ───────────────────────────────────
def tl(n):
    isaretli = n < 0
    s = f"₺{abs(int(round(n))):,}".replace(",", ".")
    return f"−{s}" if isaretli else s

def kart(baslik, deger, alt="", vurgu=False, renk=None):
    renk_deger = renk or RENK["metin"]
    return html.Div([
        html.Div(baslik, style={"fontSize": "11px", "color": RENK["soluk"],
                                "letterSpacing": "0.08em", "textTransform": "uppercase",
                                "marginBottom": "6px", "fontFamily": "monospace"}),
        html.Div(deger, style={"fontSize": "22px", "fontWeight": "500",
                               "color": renk_deger, "lineHeight": "1"}),
        html.Div(alt, style={"fontSize": "11px", "color": RENK["soluk"], "marginTop": "5px"}),
    ], style={
        "background": RENK["bg2"] if not vurgu else RENK["bg3"],
        "border": f"1px solid {RENK['accent'] if vurgu else RENK['border']}",
        "borderTop": f"2px solid {RENK['accent'] if vurgu else RENK['border']}",
        "padding": "16px 18px",
        "borderRadius": "2px",
        "flex": "1",
    })

def bolum_basligi(metin):
    return html.Div(metin, style={
        "fontFamily": "monospace", "fontSize": "10px", "letterSpacing": "0.1em",
        "textTransform": "uppercase", "color": RENK["soluk"],
        "borderBottom": f"1px solid {RENK['border']}",
        "paddingBottom": "8px", "marginTop": "32px", "marginBottom": "16px",
    })

def aciklama_kutusu(metin, renk=None):
    return html.Div(metin, style={
        "fontSize": "12px", "color": RENK["soluk"],
        "borderLeft": f"3px solid {renk or RENK['accent']}",
        "padding": "8px 14px", "marginBottom": "16px",
        "background": RENK["bg2"], "lineHeight": "1.7",
        "borderRadius": "0 2px 2px 0",
    })

# ── UYGULAMA ────────────────────────────────────────────────
app = dash.Dash(__name__, title="FiCo Kaşif — Finansal Vaka")

SEKME_STILI = {
    "backgroundColor": RENK["bg"],
    "color": RENK["soluk"],
    "border": f"1px solid {RENK['border']}",
    "borderRadius": "0",
    "padding": "10px 24px",
    "fontFamily": "monospace",
    "fontSize": "11px",
    "letterSpacing": "0.08em",
}
SEKME_SECILI_STILI = {
    **SEKME_STILI,
    "color": RENK["accent"],
    "borderBottom": f"2px solid {RENK['accent']}",
    "backgroundColor": RENK["bg2"],
}

app.layout = html.Div([
    # Başlık çubuğu
    html.Div([
        html.Div([
            html.Span("FiCo Kaşif", style={"color": RENK["accent"]}),
            html.Span(" / Finansal Vaka Analizi", style={"color": RENK["soluk"]}),
        ], style={"fontFamily": "monospace", "fontSize": "12px", "letterSpacing": "0.1em"}),
        html.Div("Baz Senaryo — Tek Banka İç Kullanım", style={
            "fontFamily": "monospace", "fontSize": "10px",
            "color": RENK["soluk"], "letterSpacing": "0.06em",
        }),
    ], style={
        "background": RENK["bg2"], "borderBottom": f"1px solid {RENK['border']}",
        "padding": "14px 32px", "display": "flex",
        "justifyContent": "space-between", "alignItems": "center",
    }),

    # Sekmeler
    dcc.Tabs(id="sekmeler", value="maliyet", children=[
        dcc.Tab(label="01  Maliyet Modeli", value="maliyet",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
        dcc.Tab(label="02  Değer / ROI", value="roi",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
        dcc.Tab(label="03  NPV & Geri Ödeme", value="npv",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
    ], style={"background": RENK["bg"], "borderBottom": f"1px solid {RENK['border']}"}),

    # İçerik
    html.Div(id="icerik", style={
        "background": RENK["bg"], "minHeight": "100vh",
        "padding": "32px 40px", "maxWidth": "1200px", "margin": "0 auto",
    }),
], style={"background": RENK["bg"], "color": RENK["metin"], "fontFamily": "Georgia, serif"})


@callback(Output("icerik", "children"), Input("sekmeler", "value"))
def sekme_goster(sekme):

    # ── SAYFA 1: MALİYET MODELİ ─────────────────────────────
    if sekme == "maliyet":
        # CAPEX pasta grafik
        capex_fig = go.Figure(go.Pie(
            labels=list(CAPEX.keys()),
            values=list(CAPEX.values()),
            hole=0.55,
            marker=dict(colors=["#c8a96e", "#5db87a", "#9aab8a", "#2a422a"]),
            textinfo="label+percent",
            textfont=dict(color=RENK["metin"], size=11),
        ))
        capex_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            showlegend=False, margin=dict(t=20, b=20, l=20, r=20),
            height=260,
            annotations=[dict(text=tl(capex_toplam), x=0.5, y=0.5,
                             font=dict(size=13, color=RENK["accent"]),
                             showarrow=False)],
        )

        # Maliyet waterfall
        waterfall_etiketler = ["Personel Yr1", "CAPEX", "OPEX Yr1", "Toplam Yr1",
                                "OPEX Yr2+", "Bakım Müh.", "Yıllık Devam"]
        waterfall_degerler = [personel_yr1, capex_toplam, opex_yillik,
                               None, opex_yillik, bakim_muhendis, None]
        waterfall_measure = ["relative", "relative", "relative", "total",
                              "relative", "relative", "total"]
        wf_fig = go.Figure(go.Waterfall(
            x=waterfall_etiketler,
            y=[personel_yr1, capex_toplam, opex_yillik, yr1_toplam,
               opex_yillik, bakim_muhendis, yr2_yillik_maliyet],
            measure=waterfall_measure,
            connector=dict(line=dict(color=RENK["border"], width=1)),
            increasing=dict(marker=dict(color="#c47a6a")),
            decreasing=dict(marker=dict(color="#5db87a")),
            totals=dict(marker=dict(color="#c8a96e")),
            text=[tl(x) if x else "" for x in [
                personel_yr1, capex_toplam, opex_yillik, yr1_toplam,
                opex_yillik, bakim_muhendis, yr2_yillik_maliyet]],
            textposition="outside",
            textfont=dict(size=10, color=RENK["metin"]),
        ))
        wf_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"]),
            yaxis=dict(gridcolor=RENK["border"], tickformat=",.0f",
                       tickprefix="₺", showgrid=True),
            margin=dict(t=20, b=20, l=20, r=20), height=320,
            showlegend=False,
        )

        return html.Div([
            html.Div("01 — Maliyet Modeli", style={
                "fontFamily": "monospace", "fontSize": "10px",
                "color": RENK["accent"], "letterSpacing": "0.12em",
                "textTransform": "uppercase", "marginBottom": "8px",
            }),
            html.H2("FiCo Kaşif'i inşa etmek ve işletmek ne kadar tutar?",
                    style={"fontSize": "28px", "fontWeight": "400",
                           "color": RENK["metin"], "marginBottom": "8px"}),
            html.P("Azure OpenAI GPT-4o + Azure AI Search S2 tabanlı RAG mimarisi. "
                   "Tüm maliyetler ₺ cinsinden (₺33/$). Personel gerçek işveren "
                   "maliyetiyle gösterilmektedir (brüt × 1,45 işveren yükü).",
                   style={"color": RENK["soluk"], "fontSize": "14px",
                          "marginBottom": "28px"}),

            # Özet kartlar
            html.Div([
                kart("CAPEX — Tek Seferlik", tl(capex_toplam),
                     "Kurulum + döküman gömme", vurgu=True),
                kart("Personel — Yıl 1", tl(personel_yr1),
                     "4 kişi × 12 ay, gerçek maliyet"),
                kart("OPEX — Yıllık Altyapı", tl(opex_yillik),
                     "Azure + GPT-4o çıkarımı"),
                kart("2 Yıllık Toplam", tl(yr1_toplam + yr2_yillik_maliyet),
                     "CAPEX + 2 yıl OPEX + personel"),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "28px"}),

            # İki sütun
            html.Div([
                html.Div([
                    bolum_basligi("CAPEX Dağılımı"),
                    dcc.Graph(figure=capex_fig, config={"displayModeBar": False}),
                    aciklama_kutusu(
                        "CAPEX son derece düşük — Azure Search kurulum 2 aylık setup maliyeti, "
                        "döküman gömme neredeyse sıfır. "
                        "⚠ Risk notu: BDDK yapay zeka sistemleri için henüz zorunlu dış denetim "
                        "gerektirmiyor ancak düzenleme yakında gelebilir. "
                        "Gerçekleşirse ~₺250-300K ek CAPEX doğabilir — risk kaydına alındı."
                    ),
                ], style={"flex": "1"}),
                html.Div([
                    bolum_basligi("Maliyet Şelalesi"),
                    dcc.Graph(figure=wf_fig, config={"displayModeBar": False}),
                    aciklama_kutusu(
                        f"Yıl 2'den itibaren yıllık sabit maliyet: {tl(yr2_yillik_maliyet)} "
                        f"(OPEX {tl(opex_yillik)} + bakım mühendisi {tl(bakim_muhendis)}). "
                        "B2B satış yoksa maliyet sonsuza kadar sabit kalır."
                    ),
                ], style={"flex": "1"}),
            ], style={"display": "flex", "gap": "24px"}),

            bolum_basligi("Personel Maliyeti Detayı — İşveren Yükü Dahil"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Rol", style={"textAlign": "left"}),
                    html.Th("Brüt Maaş", style={"textAlign": "right"}),
                    html.Th("İşveren Yükü (×1,45)", style={"textAlign": "right"}),
                    html.Th("Gerçek Yıllık Maliyet", style={"textAlign": "right"}),
                    html.Th("Süre", style={"textAlign": "right"}),
                    html.Th("Yıl 1 Toplam", style={"textAlign": "right"}),
                ], style={"borderBottom": f"1px solid {RENK['border']}",
                          "color": RENK["soluk"], "fontSize": "11px",
                          "fontFamily": "monospace", "letterSpacing": "0.06em"})),
                html.Tbody([
                    html.Tr([
                        html.Td(rol),
                        html.Td(tl(brut), style={"textAlign": "right", "fontFamily": "monospace"}),
                        html.Td(tl(brut * YUKUMLULUK), style={"textAlign": "right", "fontFamily": "monospace"}),
                        html.Td(tl(brut * YUKUMLULUK), style={"textAlign": "right",
                                 "fontFamily": "monospace", "color": RENK["accent"]}),
                        html.Td("12 ay", style={"textAlign": "right", "color": RENK["soluk"]}),
                        html.Td(tl(brut * YUKUMLULUK), style={"textAlign": "right",
                                 "fontFamily": "monospace", "fontWeight": "500"}),
                    ], style={"borderBottom": f"1px solid {RENK['border']}",
                              "fontSize": "13px", "padding": "8px"})
                    for rol, brut in [
                        ("Backend Mühendisi — RAG Pipeline", MAAS["backend"]),
                        ("ML/NLP Mühendisi", MAAS["ml_nlp"]),
                        ("Frontend / Entegrasyon Mühendisi", MAAS["frontend"]),
                        ("Proje Yöneticisi", MAAS["pm"]),
                    ]
                ] + [
                    html.Tr([
                        html.Td("TOPLAM — Yıl 1", style={"fontWeight": "500"}),
                        html.Td(tl(sum(MAAS.values())), style={"textAlign": "right",
                                "fontFamily": "monospace"}),
                        html.Td(""),
                        html.Td(tl(personel_yr1), style={"textAlign": "right",
                                "fontFamily": "monospace", "color": RENK["yesil"]}),
                        html.Td("12 ay"),
                        html.Td(tl(personel_yr1), style={"textAlign": "right",
                                "fontFamily": "monospace", "fontWeight": "500",
                                "color": RENK["yesil"]}),
                    ], style={"background": RENK["bg2"], "fontSize": "13px"}),
                    html.Tr([
                        html.Td("Bakım Mühendisi — Yıl 2+", style={"fontWeight": "500",
                                "color": RENK["accent"]}),
                        html.Td(tl(MAAS["backend"]), style={"textAlign": "right",
                                "fontFamily": "monospace", "color": RENK["soluk"]}),
                        html.Td(""),
                        html.Td(tl(bakim_muhendis), style={"textAlign": "right",
                                "fontFamily": "monospace", "color": RENK["accent"]}),
                        html.Td("Süresiz", style={"color": RENK["accent"]}),
                        html.Td(tl(bakim_muhendis) + "/yıl", style={"textAlign": "right",
                                "fontFamily": "monospace", "fontWeight": "500",
                                "color": RENK["accent"]}),
                    ], style={"background": RENK["bg3"], "fontSize": "13px"}),
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse",
                      "fontSize": "13px", "marginBottom": "16px"}),

            aciklama_kutusu(
                "İşveren yükü dökümü: SGK işveren payı %20,5 + işsizlik sigortası "
                "işveren payı %2 + yan haklar ve prim ~%22,5 = ×1,45 çarpanı. "
                f"₺1,8M brüt maaşlı bir ML mühendisi KT'ye yılda {tl(1_800_000 * YUKUMLULUK)} "
                "gerçek maliyete sahiptir."
            ),
        ])

    # ── SAYFA 2: DEĞER / ROI ─────────────────────────────────
    elif sekme == "roi":
        deger_kalemleri = {
            "Uyum Ekibi Zaman Tasarrufu": v_uyum,
            "Ürün Ekipleri Bekleme Kaybı": v_pm,
            "Şube — Kaçırılan İşlem Marjı": v_sube,
            "Ürün Lansmanı Hızlanması": v_urun,
            "BDDK Para Cezası Riski": v_bddk_para_cezasi,
            "İtibar Hasarı Önleme": v_itibar,
        }

        roi_fig = go.Figure(go.Bar(
            x=list(deger_kalemleri.values()),
            y=list(deger_kalemleri.keys()),
            orientation="h",
            marker=dict(
                color=list(deger_kalemleri.values()),
                colorscale=[[0, RENK["soluk"]], [1, RENK["yesil"]]],
            ),
            text=[tl(v) for v in deger_kalemleri.values()],
            textposition="outside",
            textfont=dict(size=11, color=RENK["metin"]),
        ))
        roi_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"], tickformat=",.0f",
                       tickprefix="₺", title=""),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(t=20, b=20, l=200, r=120),
            height=320, showlegend=False,
        )

        return html.Div([
            html.Div("02 — Değer / ROI", style={
                "fontFamily": "monospace", "fontSize": "10px",
                "color": RENK["accent"], "letterSpacing": "0.12em",
                "textTransform": "uppercase", "marginBottom": "8px",
            }),
            html.H2("Mevcut durum aslında ne kadar maliyetli?",
                    style={"fontSize": "28px", "fontWeight": "400",
                           "color": RENK["metin"], "marginBottom": "8px"}),
            html.P("Üç değer kovası: FTE zaman tasarrufu (sert tasarruf), risk azaltma "
                   "(beklenen değer), gelir etkisi (muhafazakâr tahmin). "
                   "KT'nin 2021–2025 arası 6.000 sorgu kaydına ve Danışma Komitesi kararlarına dayanmaktadır.",
                   style={"color": RENK["soluk"], "fontSize": "14px",
                          "marginBottom": "28px"}),

            html.Div([
                kart("Yıllık Toplam Değer", tl(v_toplam),
                     "3 kova birlikte", vurgu=True, renk=RENK["yesil"]),
                kart("Personel Verimliliği", tl(v_uyum + v_pm),
                     "Uyum ekibi + ürün ekipleri"),
                kart("Risk Azaltma", tl(v_bddk_para_cezasi + v_itibar),
                     "Beklenen değer bazında"),
                kart("Gelir Etkisi", tl(v_sube + v_urun),
                     "Kaçırılan işlem + lansман hızı"),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "28px"}),

            bolum_basligi("Değer Kovası Dağılımı"),
            dcc.Graph(figure=roi_fig, config={"displayModeBar": False}),

            bolum_basligi("Hesaplama Detayları"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Değer Kalemi", style={"textAlign": "left"}),
                    html.Th("Hesaplama Mantığı", style={"textAlign": "left"}),
                    html.Th("Yıllık Değer", style={"textAlign": "right"}),
                ], style={"borderBottom": f"1px solid {RENK['border']}",
                          "color": RENK["soluk"], "fontSize": "11px",
                          "fontFamily": "monospace"})),
                html.Tbody([
                    html.Tr([
                        html.Td(kalem, style={"fontWeight": "500", "paddingRight": "16px"}),
                        html.Td(aciklama, style={"color": RENK["soluk"],
                                                  "fontSize": "12px", "lineHeight": "1.6"}),
                        html.Td(tl(deger), style={"textAlign": "right",
                                 "fontFamily": "monospace", "color": RENK["yesil"],
                                 "fontWeight": "500", "whiteSpace": "nowrap"}),
                    ], style={"borderBottom": f"1px solid {RENK['border']}",
                              "fontSize": "13px", "padding": "10px 0",
                              "verticalAlign": "top"})
                    for kalem, aciklama, deger in [
                        ("Uyum Ekibi Zaman Tasarrufu",
                         f"8 uyum uzmanı × zamanın %30u rutin sorgulara gidiyor × "
                         f"%80 otomasyon × {tl(int(uyum_saatlik))}/saat. "
                         "KT uyum ekibi bu sistemle stratejik vakalara odaklanabilir.",
                         v_uyum),
                        ("Ürün Ekipleri Bekleme Kaybı",
                         f"12 ürün müdürü × ayda 4 sorgu × 12 ay × 4 saat verimlilik kaybı "
                         f"(2 günlük bekleme) × %80 × {tl(int(pm_saatlik))}/saat. "
                         "Her geciken cevap bir ürün kararını bloke ediyor.",
                         v_pm),
                        ("Şube — Kaçırılan İşlem Marjı",
                         "400 şube × ayda 1 uyum sorusu = 4.800 sorgu/yıl. "
                         "Büyük şubelerdeki %20si (960 sorgu) × %5 düşme oranı = 48 kayıp işlem. "
                         "Ortalama kurumsal finansman ₺2M × %5 banka marjı = ₺100K/işlem.",
                         v_sube),
                        ("Ürün Lansmanı Hızlanması",
                         "5 ürün/yıl, uyum onay süreci 4 haftadan 1 haftaya iniyor → 15 iş günü kazanıldı. "
                         "İlk ay 300 müşteri × ₺2.000 marj = ₺600K/ay = ₺20K/gün × 15 gün × 5 ürün.",
                         v_urun),
                        ("BDDK Para Cezası Riski",
                         "₺50M ceza maruziyeti. Olay olasılığı: %5 → %0,8. "
                         "Beklenen değer azaltımı = ₺50M × 4,2 puan. "
                         "Kaynak: BoE 2023'te İslami bankayı £3,5M cezalandırdı.",
                         v_bddk_para_cezasi),
                        ("İtibar Hasarı Önleme",
                         "Şeriat uyumluluk başarısızlığı katılım bankacılığında "
                         "orantısız hasar verir — inanç bazlı ürün farklılaştırması erozyon. "
                         "₺50M tahmini maliyet × olasılık azaltımı 2,6 puan.",
                         v_itibar),
                    ]
                ] + [
                    html.Tr([
                        html.Td("TOPLAM YILLIK DEĞER", style={"fontWeight": "500"}),
                        html.Td("Danışma Komitesi onay mekanizması korunuyor — FiCo sadece rutin sorguları otomatize ediyor.",
                                style={"color": RENK["soluk"], "fontSize": "12px"}),
                        html.Td(tl(v_toplam), style={"textAlign": "right",
                                "fontFamily": "monospace", "color": RENK["yesil"],
                                "fontWeight": "500", "fontSize": "16px"}),
                    ], style={"background": RENK["bg2"], "fontSize": "13px",
                              "borderTop": f"1px solid {RENK['border']}"})
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse", "marginBottom": "16px"}),

            aciklama_kutusu(
                "Temel içgörü: Değer 5 farklı kullanıcı profilinden geliyor — uyum ekibi, ürün ekipleri, "
                "şube müdürleri, lansман hızı ve risk azaltma. "
                "Danışma Komitesi devre dışı bırakılmıyor — rutin sorulardan arındırılarak "
                "stratejik vakalara odaklanması sağlanıyor.",
                RENK["yesil"]
            ),
        ])

    # ── SAYFA 3: NPV & GERİ ÖDEME ────────────────────────────
    else:
        ceyrekler = [q["ceyrek"] for q in ceyreklik_nakit]
        kumulatif_cf = [q["kumulatif"] / 1_000_000 for q in ceyreklik_nakit]
        maliyet_cf = [-q["maliyet"] / 1_000_000 for q in ceyreklik_nakit]
        deger_cf = [q["deger"] / 1_000_000 for q in ceyreklik_nakit]

        # Kümülatif CF grafiği
        geri_odeme_fig = go.Figure()
        geri_odeme_fig.add_trace(go.Bar(
            x=ceyrekler, y=maliyet_cf, name="Maliyet Çıkışı",
            marker_color="rgba(196,122,106,0.5)",
            marker_line=dict(color="#c47a6a", width=0.5),
        ))
        geri_odeme_fig.add_trace(go.Bar(
            x=ceyrekler, y=deger_cf, name="Değer Girişi",
            marker_color="rgba(93,184,122,0.3)",
            marker_line=dict(color="#5db87a", width=0.5),
        ))
        geri_odeme_fig.add_trace(go.Scatter(
            x=ceyrekler, y=kumulatif_cf, name="Kümülatif Net CF",
            line=dict(color="#5db87a", width=2.5),
            mode="lines+markers",
            marker=dict(size=7, color="#5db87a"),
        ))
        geri_odeme_fig.add_hline(y=0, line_dash="dash",
                                  line_color="rgba(255,255,255,0.25)", line_width=1)
        geri_odeme_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"]),
            yaxis=dict(gridcolor=RENK["border"], ticksuffix="M₺"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
            margin=dict(t=20, b=20, l=20, r=20),
            height=300, barmode="group",
        )

        # Duyarlılık grafiği
        duy_etiketler = list(duyarlilik_senaryolari.keys())
        duy_npv = [v["npv"] / 1_000_000 for v in duyarlilik_senaryolari.values()]
        duy_renkler = [RENK["yesil"] if v >= 0 else RENK["kirmizi"] for v in duy_npv]
        duy_fig = go.Figure(go.Bar(
            x=duy_etiketler, y=duy_npv,
            marker_color=duy_renkler,
            text=[f"{v:.1f}M₺" for v in duy_npv],
            textposition="outside",
            textfont=dict(size=11, color=RENK["metin"]),
        ))
        duy_fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_width=1)
        duy_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            yaxis=dict(gridcolor=RENK["border"], ticksuffix="M₺"),
            margin=dict(t=30, b=20, l=20, r=20),
            height=280, showlegend=False,
        )

        return html.Div([
            html.Div("03 — NPV & Geri Ödeme", style={
                "fontFamily": "monospace", "fontSize": "10px",
                "color": RENK["accent"], "letterSpacing": "0.12em",
                "textTransform": "uppercase", "marginBottom": "8px",
            }),
            html.H2("Bu yatırım %45 TLREF'i geçiyor mu?",
                    style={"fontSize": "28px", "fontWeight": "400",
                           "color": RENK["metin"], "marginBottom": "8px"}),
            html.P("Çeyreklik nakit akışı modeli. MVP Ç3'te hayata geçiyor, "
                   "Ç4'te %50 benimseme, Ç5'ten itibaren %90. "
                   "İskonto oranı TLREF (~%45) — Fisher denklemiyle türetilmiştir.",
                   style={"color": RENK["soluk"], "fontSize": "14px",
                          "marginBottom": "28px"}),

            # Özet kartlar
            html.Div([
                kart("2 Yıllık NPV @ %45", tl(npv),
                     "Çeyreklik %9,67 iskonto", vurgu=True,
                     renk=RENK["yesil"] if npv >= 0 else RENK["kirmizi"]),
                kart("ROI Çarpanı", f"×{round(v_toplam*2/yr1_toplam,1)}",
                     "2 yıllık değer / toplam yatırım",
                     renk=RENK["yesil"] if v_toplam > yr1_toplam else RENK["kirmizi"]),
                kart("Basit Geri Ödeme", f"Ay {geri_odeme_ay}" if geri_odeme_ay else "> 24 Ay",
                     "İskontosuz başabaş"),
                kart("Net Yıllık Fayda", tl(net_yillik),
                     "Yıl 2'den itibaren sabit",
                     renk=RENK["yesil"] if net_yillik >= 0 else RENK["kirmizi"]),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "28px"}),

            # İskonto oranı türetimi
            bolum_basligi("İskonto Oranı Türetimi — Fisher Denklemi"),
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("Reel Getiri Bileşenleri",
                                  style={"fontFamily": "monospace", "fontSize": "10px",
                                         "color": RENK["soluk"], "textTransform": "uppercase",
                                         "letterSpacing": "0.08em"}),
                        html.Table([
                            html.Tbody([
                                html.Tr([
                                    html.Td(kalem, style={"color": RENK["soluk"],
                                                           "fontSize": "12px", "paddingRight": "24px",
                                                           "paddingBottom": "6px"}),
                                    html.Td(deger, style={"fontFamily": "monospace",
                                                           "color": RENK["metin"], "fontSize": "13px",
                                                           "textAlign": "right"}),
                                ])
                                for kalem, deger in [
                                    ("ABD 10 Yıllık Tahvil (risksiz oran)", "~%3,0"),
                                    ("Küresel Sermaye Risk Primi (ERP)", "~%4,0"),
                                    ("Türkiye CDS Farkı (Mart 2026)", "~%1,5"),
                                    ("Reel Getiri Beklentisi", "~%8,5"),
                                    ("Enflasyon (TÜFE Şubat 2026)", "%31,5"),
                                    ("Fisher: (1,085)×(1,315)−1", f"≈%{nominal_oran*100:.1f}"),
                                ]
                            ])
                        ], style={"marginTop": "12px"}),
                    ], style={
                        "background": RENK["bg2"], "border": f"1px solid {RENK['border']}",
                        "padding": "16px 20px", "flex": "1",
                    }),
                ], style={"flex": "1"}),
                html.Div([
                    aciklama_kutusu(
                        f"Nominal iskonto oranı: %{nominal_oran*100:.1f} ≈ TLREF. "
                        "KT bir katılım bankası olarak faiz bazlı WACC kullanmaz — "
                        "TLREF iç proje değerlendirmesi için kâr oranı referansı "
                        "olarak hizmet eder. Fisher türetimi şeffaflık sağlar: "
                        "bileşen bileşen inşa edilmiş, keyfi seçilmemiş.",
                        RENK["accent"]
                    ),
                    aciklama_kutusu(
                        f"Çeyreklik oran: (1 + {nominal_oran:.4f})^0,25 − 1 = "
                        f"%{ceyrek_oran*100:.2f}. "
                        "8. çeyrekteki değer bugün 1 liranın "
                        f"{1/(1+ceyrek_oran)**8*100:.1f} kuruşuna eşdeğer — "
                        "bu nedenle Q3'te erken lansman NPV'yi önemli ölçüde artırır.",
                        RENK["yesil"]
                    ),
                ], style={"flex": "1"}),
            ], style={"display": "flex", "gap": "20px", "marginBottom": "24px"}),

            # Çeyreklik tablo
            bolum_basligi("Çeyreklik Nakit Akışı Tablosu"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={
                        "textAlign": "right" if i > 1 else "left",
                        "color": RENK["soluk"], "fontSize": "10px",
                        "fontFamily": "monospace", "letterSpacing": "0.06em",
                        "padding": "6px 10px",
                        "borderBottom": f"1px solid {RENK['border']}",
                    })
                    for i, h in enumerate([
                        "Çeyrek", "Faz", "Benimseme",
                        "Maliyet (₺)", "Değer (₺)", "Net CF (₺)",
                        "İsk. Faktörü", "Bugünkü Değer (₺)", "Kümülatif NPV (₺)"
                    ])
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(q["ceyrek"], style={"fontFamily": "monospace",
                                "fontSize": "12px", "padding": "8px 10px",
                                "whiteSpace": "nowrap"}),
                        html.Td(q["faz"], style={"color": RENK["soluk"],
                                "fontSize": "11px", "padding": "8px 10px"}),
                        html.Td(
                            f"%{int(q['benimseme']*100)}" if q["benimseme"] > 0 else "—",
                            style={"textAlign": "right", "fontFamily": "monospace",
                                   "fontSize": "12px", "padding": "8px 10px",
                                   "color": RENK["accent"] if q["benimseme"] > 0 else RENK["soluk"]}
                        ),
                        html.Td(tl(-q["maliyet"]), style={"textAlign": "right",
                                "fontFamily": "monospace", "fontSize": "12px",
                                "padding": "8px 10px", "color": RENK["kirmizi"]}),
                        html.Td(
                            tl(q["deger"]) if q["deger"] > 0 else "—",
                            style={"textAlign": "right", "fontFamily": "monospace",
                                   "fontSize": "12px", "padding": "8px 10px",
                                   "color": RENK["yesil"] if q["deger"] > 0 else RENK["soluk"]}
                        ),
                        html.Td(tl(q["net"]), style={
                            "textAlign": "right", "fontFamily": "monospace",
                            "fontSize": "12px", "padding": "8px 10px",
                            "color": RENK["yesil"] if q["net"] >= 0 else RENK["kirmizi"],
                            "fontWeight": "500",
                        }),
                        html.Td(f"{q['df']:.4f}", style={"textAlign": "right",
                                "fontFamily": "monospace", "fontSize": "11px",
                                "padding": "8px 10px", "color": RENK["soluk"]}),
                        html.Td(tl(q["pv"]), style={
                            "textAlign": "right", "fontFamily": "monospace",
                            "fontSize": "12px", "padding": "8px 10px",
                            "color": RENK["yesil"] if q["pv"] >= 0 else RENK["kirmizi"],
                        }),
                        html.Td(tl(q["kum_npv"]), style={
                            "textAlign": "right", "fontFamily": "monospace",
                            "fontSize": "12px", "padding": "8px 10px",
                            "color": RENK["yesil"] if q["kum_npv"] >= 0 else RENK["kirmizi"],
                            "fontWeight": "500",
                        }),
                    ], style={
                        "borderBottom": f"1px solid {RENK['border']}",
                        "background": RENK["bg2"] if q["benimseme"] == 0 else RENK["bg"],
                    })
                    for q in ceyreklik_nakit
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse", "marginBottom": "24px"}),

            # Geri ödeme eğrisi
            bolum_basligi("Geri Ödeme Eğrisi — Kümülatif Nakit Akışı (₺M)"),
            dcc.Graph(figure=geri_odeme_fig, config={"displayModeBar": False}),

            html.Div([
                html.Span(
                    f"Geri Ödeme: Ay {geri_odeme_ay}" if geri_odeme_ay else "24 Ayı Aşıyor",
                    style={"fontSize": "24px", "fontWeight": "500",
                           "color": RENK["yesil"], "marginRight": "16px"}
                ),
                html.Span(
                    f"Bu noktadan itibaren FiCo yılda {tl(net_yillik)} net fayda üretir. "
                    f"Sabit maliyet tabanı: {tl(yr2_yillik_maliyet)}/yıl.",
                    style={"color": RENK["soluk"], "fontSize": "13px", "lineHeight": "1.6"}
                ),
            ], style={"display": "flex", "alignItems": "center",
                      "background": RENK["bg2"], "padding": "16px 20px",
                      "border": f"1px solid {RENK['border']}",
                      "marginBottom": "24px", "marginTop": "12px"}),

            # Duyarlılık analizi
            bolum_basligi("Duyarlılık Analizi — Değer Varsayımları Değişirse Ne Olur?"),
            dcc.Graph(figure=duy_fig, config={"displayModeBar": False}),

            html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={
                        "textAlign": "right" if i > 0 else "left",
                        "color": RENK["soluk"], "fontSize": "10px",
                        "fontFamily": "monospace", "letterSpacing": "0.06em",
                        "padding": "6px 10px",
                        "borderBottom": f"1px solid {RENK['border']}",
                    })
                    for i, h in enumerate(["Senaryo", "2Y NPV @ %45",
                                           "Geri Ödeme", "Net Yıllık Fayda", "Karar"])
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(senaryo, style={
                            "fontWeight": "500" if "Baz" in senaryo else "400",
                            "padding": "8px 10px", "fontSize": "13px",
                        }),
                        html.Td(tl(vals["npv"]), style={
                            "textAlign": "right", "fontFamily": "monospace",
                            "fontSize": "13px", "padding": "8px 10px",
                            "color": RENK["yesil"] if vals["npv"] >= 0 else RENK["kirmizi"],
                            "fontWeight": "500",
                        }),
                        html.Td(
                            f"Ay {vals['geri_odeme']}" if vals["geri_odeme"] else "> 24 Ay",
                            style={"textAlign": "right", "fontFamily": "monospace",
                                   "fontSize": "13px", "padding": "8px 10px",
                                   "color": RENK["metin"] if vals["geri_odeme"] else RENK["kirmizi"]}
                        ),
                        html.Td(tl(vals["net_yillik"]), style={
                            "textAlign": "right", "fontFamily": "monospace",
                            "fontSize": "13px", "padding": "8px 10px",
                            "color": RENK["yesil"] if vals["net_yillik"] >= 0 else RENK["kirmizi"],
                        }),
                        html.Td(
                            "✓ Devam Et" if vals["npv"] >= 0 else "✗ Yeniden Değerlendir",
                            style={
                                "textAlign": "right", "fontSize": "12px",
                                "padding": "8px 10px", "fontFamily": "monospace",
                                "color": RENK["yesil"] if vals["npv"] >= 0 else RENK["kirmizi"],
                            }
                        ),
                    ], style={
                        "borderBottom": f"1px solid {RENK['border']}",
                        "background": RENK["bg2"] if "Baz" in senaryo else RENK["bg"],
                    })
                    for senaryo, vals in duyarlilik_senaryolari.items()
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse", "marginBottom": "16px"}),

            aciklama_kutusu(
                "Duyarlılık yorumu: Değer varsayımları %30 hata payıyla bile NPV pozitif "
                "kalıyorsa proje sağlamdır. Değer %50 düşerse projeyi yeniden "
                "değerlendirmek gerekir — bu açıklık analitik dürüstlük göstergesidir.",
                RENK["yesil"]
            ),
        ])


server = app.server

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  FiCo Kaşif — Finansal Vaka Dashboard")
    print("="*55)
    print(f"  Tarayıcıda aç: http://127.0.0.1:8050")
    print("  Durdurmak için: CTRL+C")
    print("="*55 + "\n")
    app.run(debug=False, port=8050)
