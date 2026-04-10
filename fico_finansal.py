import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
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

FX = 45
MAAS = {"backend": 1_500_000, "ml_nlp": 1_800_000, "frontend": 1_400_000, "pm": 1_400_000}
YUKUMLULUK = 1.45

personel_yr1 = sum(MAAS.values()) * YUKUMLULUK
bakim_muhendis = MAAS["backend"] * YUKUMLULUK

CAPEX = {"Azure AI Search S2 Kurulum": 43600, "Döküman Gömme (50K sayfa)": 56}
capex_toplam = sum(CAPEX.values())

OPEX_AYLIK_USD = {
    "Azure AI Search S2 (2SU)": 981, "Azure App Service P3v3": 400,
    "Azure Blob Storage": 4, "İzleme & Günlük Kaydı": 80, "Yeniden İndeksleme": 5,
}
opex_altyapi_yillik = sum(OPEX_AYLIK_USD.values()) * 12 * FX

GIRDI_TOKEN, CIKTI_TOKEN = 3_200, 300
GIRDI_FIYAT, CIKTI_FIYAT = 2.50 / 1_000_000, 10.00 / 1_000_000
sorgu_basi_maliyet = GIRDI_TOKEN * GIRDI_FIYAT + CIKTI_TOKEN * CIKTI_FIYAT
gpt_yillik = sorgu_basi_maliyet * 6_000 * 365 * FX

opex_yillik = opex_altyapi_yillik + gpt_yillik
yr2_yillik_maliyet = opex_yillik + bakim_muhendis
yr1_toplam = personel_yr1 + capex_toplam + opex_yillik

OTOMASYON = 0.80
uyum_saatlik = (1_800_000 * YUKUMLULUK) / 2_080
pm_saatlik   = (1_400_000 * YUKUMLULUK) / 2_080

v_uyum            = 8 * 2_080 * 0.30 * OTOMASYON * uyum_saatlik
v_pm              = 12 * 4 * 12 * 4 * OTOMASYON * pm_saatlik
v_sube            = 48 * 100_000
v_urun            = 5 * 15 * 20_000
v_bddk_para_cezasi = 2_100_000
v_itibar          = 1_300_000
v_toplam = v_uyum + v_pm + v_sube + v_urun + v_bddk_para_cezasi + v_itibar
net_yillik = v_toplam - yr2_yillik_maliyet

real_getiri = 0.075
enflasyon   = 0.315
nominal_oran = (1 + real_getiri) * (1 + enflasyon) - 1
ceyrek_oran  = (1 + nominal_oran) ** 0.25 - 1

maliyet_dagilim = [0.35, 0.35, 0.20, 0.05, 0, 0, 0, 0]
benimseme = [0, 0, 0, 0.50, 0.90, 0.90, 0.90, 0.90]
fazlar = ["İnşaat","İnşaat","İnşaat — MVP Hazır","Lansman %50",
          "Tam Operasyon","Tam Operasyon","Tam Operasyon","Tam Operasyon"]

personel_capex = personel_yr1 + capex_toplam
ceyreklik_nakit = []
kumulatif = npv = 0
for i in range(8):
    mal = personel_capex * maliyet_dagilim[i] + \
          (opex_yillik / 4 if i >= 3 else 0) + \
          (bakim_muhendis / 4 if i >= 4 else 0)
    deg  = (v_toplam / 4) * benimseme[i]
    net  = deg - mal
    kumulatif += net
    df   = 1 / (1 + ceyrek_oran) ** (i + 1)
    pv   = net * df
    npv += pv
    ceyreklik_nakit.append({
        "ceyrek": f"{'Yıl 1' if i < 4 else 'Yıl 2'} Ç{i % 4 + 1}",
        "faz": fazlar[i], "benimseme": benimseme[i],
        "maliyet": mal, "deger": deg, "net": net,
        "df": df, "pv": pv, "kumulatif": kumulatif, "kum_npv": npv,
    })

geri_odeme_ay = next(((i+1)*3 for i, q in enumerate(ceyreklik_nakit) if q["kumulatif"] >= 0), None)

def duyarlilik_hesapla(d):
    v = v_toplam * (1 + d)
    km, ku = [], 0
    for i in range(8):
        ml = personel_capex * maliyet_dagilim[i] + \
             (opex_yillik / 4 if i >= 3 else 0) + \
             (bakim_muhendis / 4 if i >= 4 else 0)
        ku += (v / 4) * benimseme[i] - ml
        km.append(ku)
    geri = next(((i+1)*3 for i, k in enumerate(km) if k >= 0), None)
    n = sum(((v / 4 * benimseme[i] - personel_capex * maliyet_dagilim[i] -
              (opex_yillik / 4 if i >= 3 else 0) -
              (bakim_muhendis / 4 if i >= 4 else 0)) /
             (1 + ceyrek_oran) ** (i + 1)) for i in range(8))
    return {"npv": n, "geri_odeme": geri, "net_yillik": v - yr2_yillik_maliyet}

duyarlilik_senaryolari = {
    "Baz Senaryo": duyarlilik_hesapla(0),
    "Değer −%20":  duyarlilik_hesapla(-0.20),
    "Değer −%30":  duyarlilik_hesapla(-0.30),
    "Değer −%50":  duyarlilik_hesapla(-0.50),
    "Değer +%20":  duyarlilik_hesapla(0.20),
}

# ── YARDIMCI FONKSİYONLAR ───────────────────────────────────
def tl(n):
    s = f"₺{abs(int(round(n))):,}".replace(",", ".")
    return f"−{s}" if n < 0 else s

def indir_btn(hedef_id, dosya_adi, tablo_mu=False):
    """Saf JS ile çalışan indirme butonu — Dash callback yok."""
    return html.Button(
        "↓ PNG",
        **{
            "data-dl-target":   hedef_id,
            "data-dl-filename": dosya_adi,
            "data-dl-table":    "true" if tablo_mu else "false",
        },
        style={
            "background":    "transparent",
            "border":        f"1px solid {RENK['border']}",
            "color":         RENK["soluk"],
            "fontFamily":    "monospace",
            "fontSize":      "10px",
            "letterSpacing": "0.08em",
            "padding":       "3px 10px",
            "cursor":        "pointer",
            "borderRadius":  "1px",
            "lineHeight":    "1",
            "flexShrink":    "0",
        },
    )

def bolum(metin, hedef_id=None, dosya_adi=None, tablo_mu=False):
    """Bölüm başlığı — isteğe bağlı indirme butonu sağda."""
    children = [
        html.Span(metin, style={
            "fontFamily": "monospace", "fontSize": "10px",
            "letterSpacing": "0.1em", "textTransform": "uppercase",
            "color": RENK["soluk"],
        }),
    ]
    if hedef_id:
        children.append(indir_btn(hedef_id, dosya_adi or hedef_id, tablo_mu))
    return html.Div(children, style={
        "display":        "flex",
        "justifyContent": "space-between",
        "alignItems":     "center",
        "borderBottom":   f"1px solid {RENK['border']}",
        "paddingBottom":  "8px",
        "marginTop":      "32px",
        "marginBottom":   "16px",
    })

def kart(baslik, deger, alt="", vurgu=False, renk=None):
    return html.Div([
        html.Div(baslik, style={"fontSize": "11px", "color": RENK["soluk"],
                                "letterSpacing": "0.08em", "textTransform": "uppercase",
                                "marginBottom": "6px", "fontFamily": "monospace"}),
        html.Div(deger, style={"fontSize": "22px", "fontWeight": "500",
                               "color": renk or RENK["metin"], "lineHeight": "1"}),
        html.Div(alt, style={"fontSize": "11px", "color": RENK["soluk"], "marginTop": "5px"}),
    ], style={
        "background":  RENK["bg3"] if vurgu else RENK["bg2"],
        "border":      f"1px solid {RENK['accent'] if vurgu else RENK['border']}",
        "borderTop":   f"2px solid {RENK['accent'] if vurgu else RENK['border']}",
        "padding":     "16px 18px",
        "borderRadius":"2px",
        "flex":        "1",
    })

def aciklama(metin, renk=None):
    return html.Div(metin, style={
        "fontSize": "12px", "color": RENK["soluk"],
        "borderLeft": f"3px solid {renk or RENK['accent']}",
        "padding": "8px 14px", "marginBottom": "16px",
        "background": RENK["bg2"], "lineHeight": "1.7",
        "borderRadius": "0 2px 2px 0",
    })

# ── DOWNLOAD JS (event delegation, Dash callback yok) ───────
DOWNLOAD_SCRIPT = """
<script>
(function() {
  function waitAndBind() {
    document.addEventListener('click', function(e) {
      var btn = e.target.closest('[data-dl-target]');
      if (!btn) return;
      var target   = btn.getAttribute('data-dl-target');
      var filename = btn.getAttribute('data-dl-filename') || target;
      var isTable  = btn.getAttribute('data-dl-table') === 'true';
      var el = document.getElementById(target);
      if (!el) { console.warn('FiCo DL: element not found:', target); return; }
      if (isTable) {
        if (!window.html2canvas) { alert('html2canvas henüz yüklenmedi, lütfen bekleyin.'); return; }
        html2canvas(el, { backgroundColor: '#213621', scale: 2, useCORS: true })
          .then(function(canvas) {
            var a = document.createElement('a');
            a.download = filename + '.png';
            a.href = canvas.toDataURL('image/png');
            a.click();
          });
      } else {
        var gd = el.querySelector('.js-plotly-plot') || el;
        Plotly.downloadImage(gd, { format: 'png', filename: filename, height: 520, width: 1120, scale: 2 });
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitAndBind);
  } else {
    waitAndBind();
  }
})();
</script>
"""

# ── UYGULAMA ────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="FiCo Kaşif — Finansal Vaka",
    external_scripts=["https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"],
)

# Script'i index_string'e göm
app.index_string = app.index_string.replace(
    "</body>", DOWNLOAD_SCRIPT + "</body>"
)

SEKME_STILI = {
    "backgroundColor": RENK["bg"], "color": RENK["soluk"],
    "border": f"1px solid {RENK['border']}", "borderRadius": "0",
    "padding": "10px 24px", "fontFamily": "monospace",
    "fontSize": "11px", "letterSpacing": "0.08em",
}
SEKME_SECILI_STILI = {
    **SEKME_STILI, "color": RENK["accent"],
    "borderBottom": f"2px solid {RENK['accent']}", "backgroundColor": RENK["bg2"],
}

app.layout = html.Div([
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
    dcc.Tabs(id="sekmeler", value="maliyet", children=[
        dcc.Tab(label="01  Maliyet Modeli", value="maliyet",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
        dcc.Tab(label="02  Değer / ROI",    value="roi",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
        dcc.Tab(label="03  NPV & Geri Ödeme", value="npv",
                style=SEKME_STILI, selected_style=SEKME_SECILI_STILI),
    ], style={"background": RENK["bg"], "borderBottom": f"1px solid {RENK['border']}"}),
    html.Div(id="icerik", style={
        "background": RENK["bg"], "minHeight": "100vh",
        "padding": "32px 40px", "maxWidth": "1200px", "margin": "0 auto",
    }),
], style={"background": RENK["bg"], "color": RENK["metin"], "fontFamily": "Georgia, serif"})


@callback(Output("icerik", "children"), Input("sekmeler", "value"))
def sekme_goster(sekme):

    # ── SAYFA 1: MALİYET ────────────────────────────────────
    if sekme == "maliyet":
        capex_fig = go.Figure(go.Pie(
            labels=list(CAPEX.keys()), values=list(CAPEX.values()),
            hole=0.55,
            marker=dict(colors=["#c8a96e", "#5db87a"]),
            textinfo="label+percent",
            textfont=dict(color=RENK["metin"], size=11),
        ))
        capex_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]), showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20), height=260,
            annotations=[dict(text=tl(capex_toplam), x=0.5, y=0.5,
                              font=dict(size=13, color=RENK["accent"]), showarrow=False)],
        )

        wf_fig = go.Figure(go.Waterfall(
            x=["Personel Yr1","CAPEX","OPEX Yr1","Toplam Yr1","OPEX Yr2+","Bakım Müh.","Yıllık Devam"],
            y=[personel_yr1, capex_toplam, opex_yillik, yr1_toplam,
               opex_yillik, bakim_muhendis, yr2_yillik_maliyet],
            measure=["relative","relative","relative","total","relative","relative","total"],
            connector=dict(line=dict(color=RENK["border"], width=1)),
            increasing=dict(marker=dict(color="#c47a6a")),
            decreasing=dict(marker=dict(color="#5db87a")),
            totals=dict(marker=dict(color="#c8a96e")),
            text=[tl(x) for x in [personel_yr1, capex_toplam, opex_yillik, yr1_toplam,
                                   opex_yillik, bakim_muhendis, yr2_yillik_maliyet]],
            textposition="outside", textfont=dict(size=10, color=RENK["metin"]),
        ))
        wf_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"]),
            yaxis=dict(gridcolor=RENK["border"], tickformat=",.0f", tickprefix="₺"),
            margin=dict(t=20, b=20, l=20, r=20), height=320, showlegend=False,
        )

        return html.Div([
            html.Div("01 — Maliyet Modeli", style={
                "fontFamily": "monospace", "fontSize": "10px", "color": RENK["accent"],
                "letterSpacing": "0.12em", "textTransform": "uppercase", "marginBottom": "8px",
            }),
            html.H2("FiCo Kaşif'i inşa etmek ve işletmek ne kadar tutar?", style={
                "fontSize": "28px", "fontWeight": "400",
                "color": RENK["metin"], "marginBottom": "8px",
            }),
            html.P("Azure OpenAI GPT-4o + Azure AI Search S2 tabanlı RAG mimarisi. "
                   "Tüm maliyetler ₺ cinsinden (₺45/$). Personel gerçek işveren "
                   "maliyetiyle (brüt × 1,45) gösterilmektedir.",
                   style={"color": RENK["soluk"], "fontSize": "14px", "marginBottom": "28px"}),

            html.Div([
                kart("CAPEX — Tek Seferlik", tl(capex_toplam), "Kurulum + döküman gömme", vurgu=True),
                kart("Personel — Yıl 1", tl(personel_yr1), "4 kişi × 12 ay, gerçek maliyet"),
                kart("OPEX — Yıllık Altyapı", tl(opex_yillik), "Azure + GPT-4o çıkarımı"),
                kart("2 Yıllık Toplam", tl(yr1_toplam + yr2_yillik_maliyet), "CAPEX + 2 yıl OPEX + personel"),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "28px"}),

            html.Div([
                # Sol: CAPEX pasta
                html.Div([
                    bolum("CAPEX Dağılımı", "capex-grafik", "capex_dagilimi"),
                    html.Div(id="capex-grafik", children=[
                        dcc.Graph(figure=capex_fig, config={"displayModeBar": False}),
                    ]),
                    aciklama("CAPEX son derece düşük — Azure Search kurulum + döküman gömme neredeyse sıfır. "
                             "⚠ BDDK dış denetim zorunluluğu gelebilir → ~₺250-300K ek CAPEX riski kaydedildi."),
                ], style={"flex": "1"}),
                # Sağ: Waterfall
                html.Div([
                    bolum("Maliyet Şelalesi", "waterfall-grafik", "maliyet_selalesi"),
                    html.Div(id="waterfall-grafik", children=[
                        dcc.Graph(figure=wf_fig, config={"displayModeBar": False}),
                    ]),
                    aciklama(f"Yıl 2 sabit maliyet: {tl(yr2_yillik_maliyet)} "
                             f"(OPEX {tl(opex_yillik)} + bakım müh. {tl(bakim_muhendis)})."),
                ], style={"flex": "1"}),
            ], style={"display": "flex", "gap": "24px"}),

            bolum("Personel Maliyeti Detayı — İşveren Yükü Dahil",
                  "personel-tablo", "personel_maliyeti", tablo_mu=True),
            html.Div(id="personel-tablo", style={"background": RENK["bg"]}, children=[
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"textAlign": "left" if i == 0 else "right",
                                          "borderBottom": f"1px solid {RENK['border']}",
                                          "color": RENK["soluk"], "fontSize": "11px",
                                          "fontFamily": "monospace", "letterSpacing": "0.06em",
                                          "padding": "6px 10px"})
                        for i, h in enumerate(["Rol","Brüt Maaş","İşveren Yükü (×1,45)",
                                                "Gerçek Yıllık","Süre","Yıl 1 Toplam"])
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(rol),
                            html.Td(tl(b), style={"textAlign":"right","fontFamily":"monospace"}),
                            html.Td(tl(b*YUKUMLULUK), style={"textAlign":"right","fontFamily":"monospace"}),
                            html.Td(tl(b*YUKUMLULUK), style={"textAlign":"right","fontFamily":"monospace","color":RENK["accent"]}),
                            html.Td("12 ay", style={"textAlign":"right","color":RENK["soluk"]}),
                            html.Td(tl(b*YUKUMLULUK), style={"textAlign":"right","fontFamily":"monospace","fontWeight":"500"}),
                        ], style={"borderBottom": f"1px solid {RENK['border']}", "fontSize":"13px","padding":"8px"})
                        for rol, b in [
                            ("Backend Mühendisi — RAG Pipeline", MAAS["backend"]),
                            ("ML/NLP Mühendisi", MAAS["ml_nlp"]),
                            ("Frontend / Entegrasyon Mühendisi", MAAS["frontend"]),
                            ("Proje Yöneticisi", MAAS["pm"]),
                        ]
                    ] + [
                        html.Tr([
                            html.Td("TOPLAM — Yıl 1", style={"fontWeight":"500"}),
                            html.Td(tl(sum(MAAS.values())), style={"textAlign":"right","fontFamily":"monospace"}),
                            html.Td(""), html.Td(""),
                            html.Td("12 ay"),
                            html.Td(tl(personel_yr1), style={"textAlign":"right","fontFamily":"monospace","fontWeight":"500","color":RENK["yesil"]}),
                        ], style={"background":RENK["bg2"],"fontSize":"13px"}),
                        html.Tr([
                            html.Td("Bakım Mühendisi — Yıl 2+", style={"fontWeight":"500","color":RENK["accent"]}),
                            html.Td(tl(MAAS["backend"]), style={"textAlign":"right","fontFamily":"monospace","color":RENK["soluk"]}),
                            html.Td(""), html.Td(""),
                            html.Td("Süresiz", style={"color":RENK["accent"]}),
                            html.Td(tl(bakim_muhendis)+"/yıl", style={"textAlign":"right","fontFamily":"monospace","fontWeight":"500","color":RENK["accent"]}),
                        ], style={"background":RENK["bg3"],"fontSize":"13px"}),
                    ]),
                ], style={"width":"100%","borderCollapse":"collapse","marginBottom":"16px"}),
            ]),
            aciklama(f"SGK %20,5 + işsizlik %2 + yan haklar ~%22,5 = ×1,45 çarpanı. "
                     f"₺1,8M brüt ML müh. → {tl(1_800_000 * YUKUMLULUK)} gerçek yıllık maliyet."),
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
            x=list(deger_kalemleri.values()), y=list(deger_kalemleri.keys()),
            orientation="h",
            marker=dict(color=list(deger_kalemleri.values()),
                        colorscale=[[0, RENK["soluk"]], [1, RENK["yesil"]]]),
            text=[tl(v) for v in deger_kalemleri.values()],
            textposition="outside", textfont=dict(size=11, color=RENK["metin"]),
        ))
        roi_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"], tickformat=",.0f", tickprefix="₺"),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(t=20, b=20, l=200, r=120), height=320, showlegend=False,
        )

        return html.Div([
            html.Div("02 — Değer / ROI", style={
                "fontFamily":"monospace","fontSize":"10px","color":RENK["accent"],
                "letterSpacing":"0.12em","textTransform":"uppercase","marginBottom":"8px",
            }),
            html.H2("Mevcut durum aslında ne kadar maliyetli?", style={
                "fontSize":"28px","fontWeight":"400","color":RENK["metin"],"marginBottom":"8px",
            }),
            html.P("Üç değer kovası: FTE zaman tasarrufu, risk azaltma, gelir etkisi. "
                   "KT'nin 2021–2025 arası 6.000 sorgu kaydına dayanmaktadır.",
                   style={"color":RENK["soluk"],"fontSize":"14px","marginBottom":"28px"}),

            html.Div([
                kart("Yıllık Toplam Değer", tl(v_toplam), "3 kova birlikte", vurgu=True, renk=RENK["yesil"]),
                kart("Personel Verimliliği", tl(v_uyum + v_pm), "Uyum ekibi + ürün ekipleri"),
                kart("Risk Azaltma", tl(v_bddk_para_cezasi + v_itibar), "Beklenen değer bazında"),
                kart("Gelir Etkisi", tl(v_sube + v_urun), "Kaçırılan işlem + lansman hızı"),
            ], style={"display":"flex","gap":"10px","marginBottom":"28px"}),

            bolum("Değer Kovası Dağılımı", "roi-grafik", "deger_kovalari"),
            html.Div(id="roi-grafik", children=[
                dcc.Graph(figure=roi_fig, config={"displayModeBar": False}),
            ]),

            bolum("Hesaplama Detayları", "deger-tablo", "deger_hesaplama", tablo_mu=True),
            html.Div(id="deger-tablo", style={"background":RENK["bg"]}, children=[
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"textAlign":"left" if i < 2 else "right",
                                          "borderBottom":f"1px solid {RENK['border']}",
                                          "color":RENK["soluk"],"fontSize":"11px",
                                          "fontFamily":"monospace","padding":"6px 10px"})
                        for i, h in enumerate(["Değer Kalemi","Hesaplama Mantığı","Yıllık Değer"])
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(kalem, style={"fontWeight":"500","paddingRight":"16px","padding":"10px 10px","verticalAlign":"top"}),
                            html.Td(ac, style={"color":RENK["soluk"],"fontSize":"12px","lineHeight":"1.6","padding":"10px 10px","verticalAlign":"top"}),
                            html.Td(tl(d), style={"textAlign":"right","fontFamily":"monospace","color":RENK["yesil"],"fontWeight":"500","whiteSpace":"nowrap","padding":"10px 10px","verticalAlign":"top"}),
                        ], style={"borderBottom":f"1px solid {RENK['border']}","fontSize":"13px"})
                        for kalem, ac, d in [
                            ("Uyum Ekibi Zaman Tasarrufu",
                             f"8 uzman × %30 zaman × %80 otomasyon × {tl(int(uyum_saatlik))}/saat", v_uyum),
                            ("Ürün Ekipleri Bekleme Kaybı",
                             f"12 PM × 4 sorgu/ay × 12 ay × 4 saat kayıp × %80 × {tl(int(pm_saatlik))}/saat", v_pm),
                            ("Şube — Kaçırılan İşlem Marjı",
                             "48 kayıp işlem/yıl × ₺100K/işlem (₺2M finansman × %5 marj)", v_sube),
                            ("Ürün Lansmanı Hızlanması",
                             "5 ürün/yıl × 15 gün × ₺20K/gün", v_urun),
                            ("BDDK Para Cezası Riski",
                             "₺50M maruz × 4,2pp olasılık azaltımı", v_bddk_para_cezasi),
                            ("İtibar Hasarı Önleme",
                             "₺50M tahmini maliyet × 2,6pp olasılık azaltımı", v_itibar),
                        ]
                    ] + [html.Tr([
                        html.Td("TOPLAM", style={"fontWeight":"500","padding":"10px 10px"}),
                        html.Td("Danışma Komitesi korunuyor — sadece rutin sorgular otomatize ediliyor.",
                                style={"color":RENK["soluk"],"fontSize":"12px","padding":"10px 10px"}),
                        html.Td(tl(v_toplam), style={"textAlign":"right","fontFamily":"monospace","color":RENK["yesil"],"fontWeight":"500","fontSize":"16px","padding":"10px 10px"}),
                    ], style={"background":RENK["bg2"],"borderTop":f"1px solid {RENK['border']}"})]),
                ], style={"width":"100%","borderCollapse":"collapse","marginBottom":"16px"}),
            ]),
            aciklama("Değer 5 ayrı kullanıcı profilinden geliyor. "
                     "Danışma Komitesi devre dışı bırakılmıyor — stratejik vakalara odaklanması sağlanıyor.",
                     RENK["yesil"]),
        ])

    # ── SAYFA 3: NPV & GERİ ÖDEME ────────────────────────────
    else:
        ceyrekler  = [q["ceyrek"] for q in ceyreklik_nakit]
        kum_cf     = [q["kumulatif"] / 1e6 for q in ceyreklik_nakit]
        mal_cf     = [-q["maliyet"]  / 1e6 for q in ceyreklik_nakit]
        deg_cf     = [q["deger"]     / 1e6 for q in ceyreklik_nakit]

        go_fig = go.Figure()
        go_fig.add_trace(go.Bar(x=ceyrekler, y=mal_cf, name="Maliyet Çıkışı",
                                marker_color="rgba(196,122,106,0.5)",
                                marker_line=dict(color="#c47a6a", width=0.5)))
        go_fig.add_trace(go.Bar(x=ceyrekler, y=deg_cf, name="Değer Girişi",
                                marker_color="rgba(93,184,122,0.3)",
                                marker_line=dict(color="#5db87a", width=0.5)))
        go_fig.add_trace(go.Scatter(x=ceyrekler, y=kum_cf, name="Kümülatif Net CF",
                                    line=dict(color="#5db87a", width=2.5),
                                    mode="lines+markers", marker=dict(size=7, color="#5db87a")))
        go_fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.25)", line_width=1)
        go_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor=RENK["border"]),
            yaxis=dict(gridcolor=RENK["border"], ticksuffix="M₺"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
            margin=dict(t=20, b=20, l=20, r=20), height=300, barmode="group",
        )

        duy_npv    = [v["npv"] / 1e6 for v in duyarlilik_senaryolari.values()]
        duy_renkler = [RENK["yesil"] if v >= 0 else RENK["kirmizi"] for v in duy_npv]
        duy_fig = go.Figure(go.Bar(
            x=list(duyarlilik_senaryolari.keys()), y=duy_npv,
            marker_color=duy_renkler,
            text=[f"{v:.1f}M₺" for v in duy_npv],
            textposition="outside", textfont=dict(size=11, color=RENK["metin"]),
        ))
        duy_fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_width=1)
        duy_fig.update_layout(
            paper_bgcolor="#213621", plot_bgcolor="#213621",
            font=dict(color=RENK["metin"]),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            yaxis=dict(gridcolor=RENK["border"], ticksuffix="M₺"),
            margin=dict(t=30, b=20, l=20, r=20), height=280, showlegend=False,
        )

        return html.Div([
            html.Div("03 — NPV & Geri Ödeme", style={
                "fontFamily":"monospace","fontSize":"10px","color":RENK["accent"],
                "letterSpacing":"0.12em","textTransform":"uppercase","marginBottom":"8px",
            }),
            html.H2("Bu yatırım %45 TLREF'i geçiyor mu?", style={
                "fontSize":"28px","fontWeight":"400","color":RENK["metin"],"marginBottom":"8px",
            }),
            html.P("Çeyreklik nakit akışı modeli. MVP Ç3'te, %50 benimseme Ç4'te, %90 Ç5+.",
                   style={"color":RENK["soluk"],"fontSize":"14px","marginBottom":"28px"}),

            html.Div([
                kart("2 Yıllık NPV @ %45", tl(npv), "Çeyreklik %9,67 iskonto",
                     vurgu=True, renk=RENK["yesil"] if npv >= 0 else RENK["kirmizi"]),
                kart("ROI Çarpanı", f"×{round(v_toplam*2/yr1_toplam,1)}",
                     "2 yıllık değer / toplam yatırım",
                     renk=RENK["yesil"] if v_toplam > yr1_toplam else RENK["kirmizi"]),
                kart("Basit Geri Ödeme", f"Ay {geri_odeme_ay}" if geri_odeme_ay else "> 24 Ay",
                     "İskontosuz başabaş"),
                kart("Net Yıllık Fayda", tl(net_yillik), "Yıl 2'den itibaren sabit",
                     renk=RENK["yesil"] if net_yillik >= 0 else RENK["kirmizi"]),
            ], style={"display":"flex","gap":"10px","marginBottom":"28px"}),

            # Fisher türetimi (indirme butonu yok — küçük tablo)
            html.Div([
                html.Span("İskonto Oranı Türetimi", style={
                    "fontFamily":"monospace","fontSize":"10px","letterSpacing":"0.1em",
                    "textTransform":"uppercase","color":RENK["soluk"],
                }),
            ], style={"borderBottom":f"1px solid {RENK['border']}","paddingBottom":"8px",
                      "marginTop":"32px","marginBottom":"16px"}),
            html.Div([
                html.Div([
                    html.Table(html.Tbody([
                        html.Tr([
                            html.Td(k, style={"color":RENK["soluk"],"fontSize":"12px","paddingRight":"24px","paddingBottom":"6px"}),
                            html.Td(v, style={"fontFamily":"monospace","color":RENK["metin"],"fontSize":"13px","textAlign":"right"}),
                        ])
                        for k, v in [
                            ("ABD 10Y (risksiz)", "~%3,0"),
                            ("Küresel ERP", "~%4,0"),
                            ("Türkiye CDS", "~%1,5"),
                            ("Reel getiri", "~%8,5"),
                            ("TÜFE Şub 2026", "%31,5"),
                            ("Fisher sonucu", f"≈%{nominal_oran*100:.1f}"),
                        ]
                    ])),
                ], style={"background":RENK["bg2"],"border":f"1px solid {RENK['border']}","padding":"16px 20px","flex":"1"}),
                html.Div([
                    aciklama(f"Nominal oran %{nominal_oran*100:.1f} ≈ TLREF. "
                             "KT katılım bankası olduğu için faiz bazlı WACC kullanılmaz.", RENK["accent"]),
                    aciklama(f"Çeyreklik: {ceyrek_oran*100:.2f}%. "
                             f"8. çeyrekteki ₺1 bugün {1/(1+ceyrek_oran)**8*100:.1f} kuruşa eşdeğer.", RENK["yesil"]),
                ], style={"flex":"1"}),
            ], style={"display":"flex","gap":"20px","marginBottom":"24px"}),

            bolum("Çeyreklik Nakit Akışı Tablosu", "ceyreklik-tablo", "ceyreklik_nakit_akisi", tablo_mu=True),
            html.Div(id="ceyreklik-tablo", style={"background":RENK["bg"]}, children=[
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={
                            "textAlign":"right" if i > 1 else "left",
                            "color":RENK["soluk"],"fontSize":"10px","fontFamily":"monospace",
                            "letterSpacing":"0.06em","padding":"6px 10px",
                            "borderBottom":f"1px solid {RENK['border']}",
                        })
                        for i, h in enumerate(["Çeyrek","Faz","Benimseme",
                                               "Maliyet (₺)","Değer (₺)","Net CF (₺)",
                                               "İsk. F.","BD (₺)","Kümülatif NPV (₺)"])
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(q["ceyrek"], style={"fontFamily":"monospace","fontSize":"12px","padding":"7px 10px","whiteSpace":"nowrap"}),
                            html.Td(q["faz"],    style={"color":RENK["soluk"],"fontSize":"11px","padding":"7px 10px"}),
                            html.Td(f"%{int(q['benimseme']*100)}" if q["benimseme"] else "—",
                                    style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px",
                                           "color":RENK["accent"] if q["benimseme"] else RENK["soluk"]}),
                            html.Td(tl(-q["maliyet"]), style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px","color":RENK["kirmizi"]}),
                            html.Td(tl(q["deger"]) if q["deger"] else "—",
                                    style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px",
                                           "color":RENK["yesil"] if q["deger"] else RENK["soluk"]}),
                            html.Td(tl(q["net"]), style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px","fontWeight":"500",
                                                         "color":RENK["yesil"] if q["net"] >= 0 else RENK["kirmizi"]}),
                            html.Td(f"{q['df']:.4f}", style={"textAlign":"right","fontFamily":"monospace","fontSize":"11px","padding":"7px 10px","color":RENK["soluk"]}),
                            html.Td(tl(q["pv"]),  style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px",
                                                         "color":RENK["yesil"] if q["pv"] >= 0 else RENK["kirmizi"]}),
                            html.Td(tl(q["kum_npv"]), style={"textAlign":"right","fontFamily":"monospace","fontSize":"12px","padding":"7px 10px","fontWeight":"500",
                                                              "color":RENK["yesil"] if q["kum_npv"] >= 0 else RENK["kirmizi"]}),
                        ], style={"borderBottom":f"1px solid {RENK['border']}",
                                  "background":RENK["bg2"] if q["benimseme"] == 0 else RENK["bg"]})
                        for q in ceyreklik_nakit
                    ]),
                ], style={"width":"100%","borderCollapse":"collapse","marginBottom":"0"}),
            ]),

            bolum("Geri Ödeme Eğrisi", "geri-odeme-grafik", "geri_odeme_egrisi"),
            html.Div(id="geri-odeme-grafik", children=[
                dcc.Graph(figure=go_fig, config={"displayModeBar": False}),
            ]),
            html.Div([
                html.Span(f"Geri Ödeme: Ay {geri_odeme_ay}" if geri_odeme_ay else "24 Ayı Aşıyor",
                          style={"fontSize":"24px","fontWeight":"500","color":RENK["yesil"],"marginRight":"16px"}),
                html.Span(f"Bu noktadan itibaren FiCo yılda {tl(net_yillik)} net fayda üretir.",
                          style={"color":RENK["soluk"],"fontSize":"13px","lineHeight":"1.6"}),
            ], style={"display":"flex","alignItems":"center","background":RENK["bg2"],
                      "padding":"16px 20px","border":f"1px solid {RENK['border']}",
                      "marginBottom":"24px","marginTop":"12px"}),

            bolum("Duyarlılık Analizi", "duyarlilik-grafik", "duyarlilik_analizi"),
            html.Div(id="duyarlilik-grafik", children=[
                dcc.Graph(figure=duy_fig, config={"displayModeBar": False}),
            ]),

            bolum("Duyarlılık Tablosu", "duyarlilik-tablo", "duyarlilik_tablo", tablo_mu=True),
            html.Div(id="duyarlilik-tablo", style={"background":RENK["bg"]}, children=[
                html.Table([
                    html.Thead(html.Tr([
                        html.Th(h, style={"textAlign":"right" if i > 0 else "left",
                                          "color":RENK["soluk"],"fontSize":"10px","fontFamily":"monospace",
                                          "letterSpacing":"0.06em","padding":"6px 10px",
                                          "borderBottom":f"1px solid {RENK['border']}"})
                        for i, h in enumerate(["Senaryo","2Y NPV @ %45","Geri Ödeme","Net Yıllık Fayda","Karar"])
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(s, style={"fontWeight":"500" if "Baz" in s else "400","padding":"8px 10px","fontSize":"13px"}),
                            html.Td(tl(v["npv"]), style={"textAlign":"right","fontFamily":"monospace","fontSize":"13px","padding":"8px 10px",
                                                          "color":RENK["yesil"] if v["npv"] >= 0 else RENK["kirmizi"],"fontWeight":"500"}),
                            html.Td(f"Ay {v['geri_odeme']}" if v["geri_odeme"] else "> 24 Ay",
                                    style={"textAlign":"right","fontFamily":"monospace","fontSize":"13px","padding":"8px 10px",
                                           "color":RENK["metin"] if v["geri_odeme"] else RENK["kirmizi"]}),
                            html.Td(tl(v["net_yillik"]), style={"textAlign":"right","fontFamily":"monospace","fontSize":"13px","padding":"8px 10px",
                                                                  "color":RENK["yesil"] if v["net_yillik"] >= 0 else RENK["kirmizi"]}),
                            html.Td("✓ Devam Et" if v["npv"] >= 0 else "✗ Yeniden Değerlendir",
                                    style={"textAlign":"right","fontSize":"12px","padding":"8px 10px","fontFamily":"monospace",
                                           "color":RENK["yesil"] if v["npv"] >= 0 else RENK["kirmizi"]}),
                        ], style={"borderBottom":f"1px solid {RENK['border']}",
                                  "background":RENK["bg2"] if "Baz" in s else RENK["bg"]})
                        for s, v in duyarlilik_senaryolari.items()
                    ]),
                ], style={"width":"100%","borderCollapse":"collapse","marginBottom":"16px"}),
            ]),
            aciklama("%30 hata payıyla NPV pozitif kalıyorsa proje sağlamdır. "
                     "Değer %50 düşerse yeniden değerlendirme gerekir.", RENK["yesil"]),
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
