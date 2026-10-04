# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama

_Oluşturma: 2026-10-04T11:13:46.281656+00:00 · dönem: 2016-10-05 → 2026-09-30 · 5 iş gününde bir değerlendirme_

Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.

## 1) TEPE / DİP TESTİ — sistem "dipten al, tepeden sat" yapıyor mu?
Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı (zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).

| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |
|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | +0.50 | +29.4 (n=30) | -38.4 (n=82) | %+1.8 | %+1.8 |
| Altın (XAU) | +0.37 | +6.0 (n=126) | -44.6 (n=19) | %+5.8 | %+4.0 |
| Bakır (HG) | +0.42 | +14.5 (n=102) | -40.0 (n=20) | %+3.6 | %+4.5 |
| Gümüş (XAG) | +0.54 | +19.8 (n=59) | -38.9 (n=33) | %+11.6 | %+5.1 |
| Ham Petrol (WTI) | +0.06 | +9.2 (n=92) | -11.8 (n=40) | %+3.1 | %+15.0 |
| Kripto (BTC) | +0.51 | +20.8 (n=119) | -28.2 (n=72) | %+35.1 | %+5.1 |
| Nasdaq 100 (NQ) | +0.51 | +9.1 (n=288) | -49.9 (n=17) | %+3.3 | %+7.4 |
| S&P 500 (SPX) | +0.54 | +10.3 (n=289) | -68.9 (n=11) | %+2.2 | %+9.8 |

## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?
IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. |t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).

| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |
|---|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | **TOPLAM SKOR** | +0.093 | +0.103 | +0.099 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | makro | +0.072 | +0.111 | +0.157 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | piyasa (trend+zirve yakınlığı) | +0.057 | +0.055 | +0.004 | +0.4 | 510 |
| ABD Tahvili / Faiz (TLT) | risk döngüsü | -0.005 | -0.017 | -0.048 | -0.1 | 510 |
| Altın (XAU) | **TOPLAM SKOR** | -0.062 | -0.134 | -0.078 | -0.9 | 510 |
| Altın (XAU) | makro | -0.105 | -0.165 | -0.095 | -1.1 | 510 |
| Altın (XAU) | piyasa (trend+zirve yakınlığı) | +0.005 | -0.025 | -0.003 | -0.2 | 510 |
| Altın (XAU) | risk döngüsü | +0.022 | -0.096 | -0.138 | -0.6 | 510 |
| Bakır (HG) | **TOPLAM SKOR** | -0.085 | -0.098 | +0.011 | -0.6 | 510 |
| Bakır (HG) | makro | -0.096 | -0.093 | +0.017 | -0.6 | 510 |
| Bakır (HG) | piyasa (trend+zirve yakınlığı) | -0.026 | -0.000 | +0.007 | -0.0 | 510 |
| Bakır (HG) | risk döngüsü | +0.063 | +0.072 | +0.140 | +0.5 | 510 |
| Gümüş (XAG) | **TOPLAM SKOR** | -0.061 | -0.072 | -0.046 | -0.5 | 510 |
| Gümüş (XAG) | makro | -0.069 | -0.069 | -0.081 | -0.4 | 510 |
| Gümüş (XAG) | piyasa (trend+zirve yakınlığı) | -0.022 | -0.036 | -0.004 | -0.2 | 510 |
| Gümüş (XAG) | risk döngüsü | +0.018 | +0.071 | +0.152 | +0.5 | 510 |
| Ham Petrol (WTI) | **TOPLAM SKOR** | +0.020 | +0.035 | +0.117 | +0.2 | 510 |
| Ham Petrol (WTI) | makro | -0.036 | +0.023 | +0.117 | +0.2 | 510 |
| Ham Petrol (WTI) | piyasa (trend+zirve yakınlığı) | +0.058 | +0.020 | +0.028 | +0.1 | 510 |
| Ham Petrol (WTI) | risk döngüsü | +0.116 | +0.079 | +0.015 | +0.5 | 510 |
| Kripto (BTC) | **TOPLAM SKOR** | +0.249 | +0.389 | +0.301 | +2.5 | 510 |
| Kripto (BTC) | makro | +0.222 | +0.369 | +0.288 | +2.4 | 510 |
| Kripto (BTC) | piyasa (trend+zirve yakınlığı) | +0.056 | +0.075 | +0.046 | +0.5 | 510 |
| Kripto (BTC) | risk döngüsü | +0.127 | +0.255 | +0.262 | +1.7 | 510 |
| Nasdaq 100 (NQ) | **TOPLAM SKOR** | +0.104 | +0.133 | +0.167 | +0.9 | 510 |
| Nasdaq 100 (NQ) | makro | +0.152 | +0.220 | +0.231 | +1.4 | 510 |
| Nasdaq 100 (NQ) | piyasa (trend+zirve yakınlığı) | -0.057 | -0.126 | -0.050 | -0.8 | 510 |
| Nasdaq 100 (NQ) | risk döngüsü | +0.068 | +0.050 | +0.098 | +0.3 | 510 |
| S&P 500 (SPX) | **TOPLAM SKOR** | +0.032 | +0.078 | +0.100 | +0.5 | 510 |
| S&P 500 (SPX) | makro | +0.057 | +0.140 | +0.158 | +0.9 | 510 |
| S&P 500 (SPX) | piyasa (trend+zirve yakınlığı) | -0.056 | -0.092 | -0.075 | -0.6 | 510 |
| S&P 500 (SPX) | risk döngüsü | +0.042 | +0.069 | +0.094 | +0.5 | 510 |

## 3) Etiket isabeti (60 gün sonrası)

| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |
|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | %41 · %-1.0 (208) | %59 · %-1.6 (140) | %44 · %-0.8 |
| Altın (XAU) | %61 · %+2.9 (179) | %35 · %+3.3 (150) | %65 · %+3.3 |
| Bakır (HG) | %60 · %+4.0 (113) | %37 · %+3.6 (65) | %59 · %+2.9 |
| Gümüş (XAG) | %65 · %+5.7 (144) | %32 · %+5.1 (103) | %57 · %+4.3 |
| Ham Petrol (WTI) | %54 · %+6.9 (152) | %45 · %+11.2 (69) | %53 · %+3.9 |
| Kripto (BTC) | %64 · %+31.5 (223) | %59 · %-1.2 (113) | %59 · %+20.5 |
| Nasdaq 100 (NQ) | %70 · %+3.8 (195) | %42 · %+2.3 (136) | %74 · %+4.7 |
| S&P 500 (SPX) | %78 · %+3.4 (171) | %39 · %+2.6 (114) | %76 · %+3.2 |

## 4) Rejim başlangıcı sonrası getiriler — rejim çarpanları doğru yönde mi?
Her rejim ilk onaylandığında sonraki 60 iş günü getirisi (ortalama) ve modelin o rejimde verdiği çarpan. Çarpan < 1 (azalt) iken getiri güçlü pozitifse, rejim kuralı **dipte satıyor** demektir.

| Rejim | Başlangıç sayısı | Altın 60g (çarpan) | Gümüş 60g (çarpan) | Nasdaq 100 60g (çarpan) | S&P 500 60g (çarpan) | Kripto 60g (çarpan) | Ham Petrol 60g (çarpan) | Bakır 60g (çarpan) | ABD Tahvili / Faiz 60g (çarpan) |
|---|---|---|---|---|---|---|---|---|---|
| 1: Küresel Enflasyon & Stagflasyon Şoku | 31 | %-0.1 (1.25x) | %+0.9 (1.10x) | %+5.0 (0.40x) | %+3.6 (0.45x) | %+3.6 (0.35x) | %+6.1 (1.35x) | %+0.7 (0.85x) | %-3.1 (0.30x) |
| 2: Sistemik Likidite Şoku & Carry Çöküşü | 28 | %+2.5 (0.80x) | %+2.9 (0.60x) | %+6.2 (0.25x) | %+4.4 (0.30x) | %+7.1 (0.20x) | %+4.1 (0.50x) | %-1.1 (0.50x) | %-2.9 (0.70x) |
| 3: Reel Faiz Şoku | 27 | %+2.1 (0.65x) | %+4.4 (0.60x) | %+6.1 (0.35x) | %+4.6 (0.50x) | %+8.8 (0.35x) | %+3.1 (0.80x) | %+0.2 (0.75x) | %-0.1 (0.30x) |
| 4: Kredi Temerrüt Baskısı | 1 | %+8.3 (1.15x) | %+23.8 (0.85x) | %+29.7 (0.35x) | %+21.7 (0.35x) | %+27.7 (0.25x) | %+5.7 (0.60x) | %+15.6 (0.55x) | %-5.9 (1.20x) |
| 5: Küresel Likidite Rallisi (Risk-On) | 2 | %+17.0 (0.90x) | %+24.2 (1.05x) | %+7.7 (1.40x) | %+8.9 (1.35x) | %+65.1 (1.30x) | %+18.8 (0.90x) | %+14.7 (1.10x) | %-4.7 (1.10x) |
| Koşulsuz (tüm günler) | — | %+2.0 | %+2.4 | %+4.2 | %+2.9 | %+19.0 | %+2.1 | %+1.2 | %-0.0 |

## 5) Portföy testi — hedef ağırlıklar vs eşit ağırlık (örneklem dışı, işlem ertesi gün)

- **🎯 Min-DD rejim portföyü (yeni hedef, her çeyrek yalnızca geçmiş veriyle yeniden optimize):** yıllık getiri %+5.5 · volatilite %6.5 · Sharpe 0.84 · maks. düşüş %-16.0
- **🎯 Min-DD rejim portföyü — %100 yatırımda (nakitsiz):** yıllık getiri %+10.7 · volatilite %15.3 · Sharpe 0.70 · maks. düşüş %-39.8
- **Eski hedef (sinyal × rejim çarpanı + nakit):** yıllık getiri %+9.7 · volatilite %9.1 · Sharpe 1.07 · maks. düşüş %-22.4
- **Eşit ağırlık 8 varlık (%100 yatırımda):** yıllık getiri %+13.8 · volatilite %20.9 · Sharpe 0.66 · maks. düşüş %-57.6
- Ortalama nakit payı: %56. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)

## 6) Faktör bazında IC — her makro gösterge her varlıkta doğru yönde mi?
Değer = (gösterge z-skoru × modeldeki varlık kutbu) ile sonraki 60 iş günü getirisinin sıra korelasyonu. **Pozitif** = gösterge o varlığı doğru yöne itiyor; **negatif** = ters itiyor. ± işaretli değerlerde |t| ≥ 2 (anlamlı) olanlar **kalın**.

| Gösterge | ABD Tahvili / Faiz | Altın | Bakır | Gümüş | Ham Petrol | Kripto | Nasdaq 100 | S&P 500 |
|---|---|---|---|---|---|---|---|---|
| Dolar Endeksi Zayıflığı (DXY) | -0.10 | -0.17 | +0.10 | +0.00 | +0.26 | +0.23 | +0.25 | +0.28 |
| G4 Küresel Süper Likidite (Fed+ECB+BoJ) | +0.06 | -0.09 | +0.20 | -0.01 | +0.29 | **+0.33** | **+0.31** | +0.29 |
| Reel Faiz Seviyesi / Tahvil Taşıma Getirisi (TLT değerleme) | +0.10 | — | — | — | — | — | — | — |
| Reel Faiz İndirgeme İvmesi (10Y TIPS) | +0.01 | +0.05 | +0.10 | +0.05 | +0.11 | **+0.31** | +0.19 | +0.21 |
| 10Y Breakeven Enflasyon İvmesi | +0.15 | -0.08 | -0.22 | -0.14 | -0.20 | **-0.37** | +0.27 | +0.23 |
| 5Y5Y İleri Enflasyon Beklentisi (T5YIFR) | +0.08 | +0.01 | -0.25 | -0.05 | -0.24 | — | +0.21 | +0.17 |
| Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y) | +0.14 | +0.19 | +0.10 | +0.24 | +0.02 | **+0.35** | +0.22 | +0.23 |
| Yüksek Getirili Kredi Stresi (HY OAS) | +0.04 | **-0.32** | +0.10 | +0.17 | -0.10 | -0.13 | -0.06 | -0.00 |
| MOVE Endeksi (Tahvil Volatilitesi) | +0.15 | +0.15 | +0.11 | -0.12 | +0.21 | +0.16 | -0.04 | -0.02 |
| VIX Endeksi (Hisse Volatilitesi) | +0.17 | -0.16 | -0.19 | -0.10 | -0.14 | +0.11 | -0.17 | -0.23 |
| Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y) | -0.18 | -0.26 | +0.29 | +0.26 | +0.10 | +0.25 | +0.30 | **+0.34** |
| Öncü İstihdam (ICSA) | **-0.35** | -0.09 | -0.23 | -0.04 | -0.25 | +0.07 | -0.02 | -0.11 |
| Hazine Nakit / Banka Rezervleri (WRESBAL) | **-0.35** | -0.17 | +0.11 | -0.04 | +0.14 | +0.08 | -0.04 | +0.03 |

## 8) UZUN VADELİ DÖNGÜ SİNYALİ (dipten al-unut / tepeden sat-unut) — varlık bazında örneklem dışı
Her yıl yalnızca geçmiş veriyle en iyi parametre seçilir (3y/2y değer ortalaması, dip/tepe bant genişliği, dönüş teyidi, yeniden giriş kuralı) ve ERTESİ YIL uygulanır. Satış = nakde geç (kaldıraç/açığa satış yok). Karşılaştırma aynı dönemde al-tut ile.

| Varlık | Döngü yıllık | Döngü maks. DD | Al-tut yıllık | Al-tut maks. DD | Kârlı al-sat turu | SAT sonrası 120g düşüş isabeti | Piyasada kalma | Canlı parametre |
|---|---|---|---|---|---|---|---|---|
| Altın (XAU) | %+2.7 | %-10.2 | %+12.2 | %-24.9 | %100 (3) | %67 (3) | %13 | L=504, bant 20/80, teyit=yok, giriş=mean |
| Gümüş (XAG) | %+6.5 | %-19.9 | %+13.0 | %-51.4 | %100 (3) | %0 (3) | %18 | L=504, bant 10/90, teyit=yok, giriş=mean |
| Nasdaq 100 (NQ) | %+15.0 | %-21.9 | %+17.9 | %-35.6 | %100 (4) | %0 (5) | %64 | L=756, bant 10/90, teyit=yok, giriş=bottom |
| S&P 500 (SPX) | %+7.0 | %-34.1 | %+11.9 | %-34.1 | %100 (3) | %0 (4) | %61 | L=504, bant 15/85, teyit=var, giriş=bottom |
| Kripto (BTC) | %+43.1 | %-59.9 | %+34.2 | %-76.6 | %100 (1) | %0 (1) | %86 | L=756, bant 20/80, teyit=yok, giriş=bottom |
| Ham Petrol (WTI) | %+4.3 | %-47.2 | %+5.9 | %-86.9 | %33 (3) | %25 (4) | %28 | L=756, bant 10/90, teyit=var, giriş=mean |
| Bakır (HG) | %+5.8 | %-23.1 | %+9.2 | %-35.6 | %100 (2) | %33 (3) | %36 | L=756, bant 10/90, teyit=yok, giriş=mean |

## 7) PORTFÖY STRATEJİSİ YARIŞI (örneklem dışı) — canlı hedef buradan seçilir
Öncelik = minimum düşüş: maks. düşüşü %12 içinde kalanlar arasından en yüksek yıllık getirili strateji canlıya alınır (hiçbiri sığmazsa en küçük düşüşlü). Döngü stratejisi, varlık döngü sinyallerinin ÖRNEKLEM DIŞI hâlini kullanır. Haftalık dengeleme, ertesi gün işlem, 5 bps maliyet, kaldıraç yok.

| Strateji | Yıllık getiri | Maks. düşüş | Calmar | Sharpe | Kazançlı ay oranı | Kazançlı yıl oranı |
|---|---|---|---|---|---|---|
| Risk paritesi · %10 vol hedefi | %+10.0 | %-20.5 | 0.49 | 1.01 | %64 | %82 |
| Risk paritesi + 200g trend · %10 vol hedefi 🏆 **CANLI SEÇİM** | %+9.8 | %-11.2 | 0.88 | 1.25 | %64 | %82 |
| Risk paritesi · rejime göre vol hedefi | %+9.6 | %-16.3 | 0.59 | 1.08 | %63 | %82 |
| Risk paritesi + 200g trend · rejime göre vol hedefi | %+9.4 | %-10.3 | 0.90 | 1.25 | %64 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · %10 vol hedefi | %+8.5 | %-8.4 | 1.01 | 1.45 | %64 | %73 |
| Risk paritesi + 200g trend · rejime göre vol + düşüş freni | %+8.4 | %-9.1 | 0.92 | 1.18 | %60 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol hedefi | %+8.2 | %-7.2 | 1.14 | 1.49 | %63 | %73 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol + düşüş freni | %+7.2 | %-7.2 | 1.01 | 1.38 | %63 | %73 |
| Risk paritesi · rejime göre vol + düşüş freni | %+7.2 | %-11.0 | 0.65 | 0.97 | %63 | %82 |
| Eşit ağırlık 8 varlık (referans) | %+13.6 | %-57.8 | 0.24 | 0.65 | %65 | %73 |

## Sınırlar
- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).
- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.
- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok.
