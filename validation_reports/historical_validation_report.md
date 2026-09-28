# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama

_Oluşturma: 2026-09-28T10:56:38.487977+00:00 · dönem: 2016-09-28 → 2026-09-23 · 5 iş gününde bir değerlendirme_

Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.

## 1) TEPE / DİP TESTİ — sistem "dipten al, tepeden sat" yapıyor mu?
Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı (zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).

| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |
|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | +0.50 | +29.4 (n=30) | -38.2 (n=81) | %+1.8 | %+1.8 |
| Altın (XAU) | +0.36 | +6.0 (n=126) | -44.6 (n=19) | %+5.8 | %+4.0 |
| Bakır (HG) | +0.42 | +14.5 (n=102) | -40.0 (n=20) | %+3.6 | %+4.5 |
| Gümüş (XAG) | +0.53 | +19.8 (n=59) | -38.9 (n=33) | %+11.6 | %+5.1 |
| Ham Petrol (WTI) | +0.06 | +9.2 (n=92) | -11.8 (n=40) | %+3.1 | %+15.0 |
| Kripto (BTC) | +0.51 | +20.8 (n=119) | -28.2 (n=72) | %+35.1 | %+4.6 |
| Nasdaq 100 (NQ) | +0.51 | +9.4 (n=288) | -49.9 (n=17) | %+3.3 | %+7.4 |
| S&P 500 (SPX) | +0.54 | +10.3 (n=290) | -68.9 (n=11) | %+2.2 | %+9.8 |

## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?
IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. |t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).

| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |
|---|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | **TOPLAM SKOR** | +0.090 | +0.098 | +0.098 | +0.6 | 510 |
| ABD Tahvili / Faiz (TLT) | makro | +0.067 | +0.106 | +0.154 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | piyasa (trend+zirve yakınlığı) | +0.056 | +0.055 | +0.006 | +0.4 | 510 |
| ABD Tahvili / Faiz (TLT) | risk döngüsü | -0.001 | -0.017 | -0.049 | -0.1 | 510 |
| Altın (XAU) | **TOPLAM SKOR** | -0.061 | -0.129 | -0.078 | -0.8 | 510 |
| Altın (XAU) | makro | -0.105 | -0.160 | -0.092 | -1.0 | 510 |
| Altın (XAU) | piyasa (trend+zirve yakınlığı) | +0.007 | -0.022 | -0.004 | -0.1 | 510 |
| Altın (XAU) | risk döngüsü | +0.023 | -0.096 | -0.145 | -0.6 | 510 |
| Bakır (HG) | **TOPLAM SKOR** | -0.086 | -0.095 | +0.012 | -0.6 | 510 |
| Bakır (HG) | makro | -0.095 | -0.093 | +0.015 | -0.6 | 510 |
| Bakır (HG) | piyasa (trend+zirve yakınlığı) | -0.028 | +0.004 | +0.010 | +0.0 | 510 |
| Bakır (HG) | risk döngüsü | +0.062 | +0.072 | +0.140 | +0.5 | 510 |
| Gümüş (XAG) | **TOPLAM SKOR** | -0.058 | -0.066 | -0.041 | -0.4 | 510 |
| Gümüş (XAG) | makro | -0.068 | -0.065 | -0.078 | -0.4 | 510 |
| Gümüş (XAG) | piyasa (trend+zirve yakınlığı) | -0.017 | -0.031 | +0.000 | -0.2 | 510 |
| Gümüş (XAG) | risk döngüsü | +0.017 | +0.071 | +0.158 | +0.5 | 510 |
| Ham Petrol (WTI) | **TOPLAM SKOR** | +0.018 | +0.036 | +0.116 | +0.2 | 510 |
| Ham Petrol (WTI) | makro | -0.038 | +0.024 | +0.116 | +0.2 | 510 |
| Ham Petrol (WTI) | piyasa (trend+zirve yakınlığı) | +0.059 | +0.021 | +0.028 | +0.1 | 510 |
| Ham Petrol (WTI) | risk döngüsü | +0.115 | +0.077 | +0.015 | +0.5 | 510 |
| Kripto (BTC) | **TOPLAM SKOR** | +0.249 | +0.391 | +0.302 | +2.6 | 510 |
| Kripto (BTC) | makro | +0.225 | +0.373 | +0.290 | +2.4 | 510 |
| Kripto (BTC) | piyasa (trend+zirve yakınlığı) | +0.053 | +0.071 | +0.044 | +0.5 | 510 |
| Kripto (BTC) | risk döngüsü | +0.127 | +0.255 | +0.264 | +1.7 | 510 |
| Nasdaq 100 (NQ) | **TOPLAM SKOR** | +0.105 | +0.131 | +0.168 | +0.9 | 510 |
| Nasdaq 100 (NQ) | makro | +0.153 | +0.217 | +0.233 | +1.4 | 510 |
| Nasdaq 100 (NQ) | piyasa (trend+zirve yakınlığı) | -0.056 | -0.127 | -0.053 | -0.8 | 510 |
| Nasdaq 100 (NQ) | risk döngüsü | +0.067 | +0.051 | +0.096 | +0.3 | 510 |
| S&P 500 (SPX) | **TOPLAM SKOR** | +0.030 | +0.078 | +0.102 | +0.5 | 510 |
| S&P 500 (SPX) | makro | +0.054 | +0.139 | +0.159 | +0.9 | 510 |
| S&P 500 (SPX) | piyasa (trend+zirve yakınlığı) | -0.056 | -0.092 | -0.077 | -0.6 | 510 |
| S&P 500 (SPX) | risk döngüsü | +0.041 | +0.070 | +0.093 | +0.5 | 510 |

## 3) Etiket isabeti (60 gün sonrası)

| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |
|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | %41 · %-0.9 (207) | %59 · %-1.6 (139) | %44 · %-0.8 |
| Altın (XAU) | %60 · %+2.8 (179) | %35 · %+3.2 (150) | %65 · %+3.3 |
| Bakır (HG) | %60 · %+3.9 (112) | %38 · %+3.6 (64) | %59 · %+2.9 |
| Gümüş (XAG) | %64 · %+5.6 (144) | %33 · %+4.9 (103) | %57 · %+4.3 |
| Ham Petrol (WTI) | %54 · %+6.8 (151) | %46 · %+11.0 (68) | %53 · %+3.9 |
| Kripto (BTC) | %64 · %+31.6 (224) | %59 · %-1.2 (113) | %59 · %+20.5 |
| Nasdaq 100 (NQ) | %70 · %+3.8 (195) | %42 · %+2.3 (135) | %74 · %+4.7 |
| S&P 500 (SPX) | %78 · %+3.4 (171) | %39 · %+2.6 (114) | %76 · %+3.2 |

## 4) Rejim başlangıcı sonrası getiriler — rejim çarpanları doğru yönde mi?
Her rejim ilk onaylandığında sonraki 60 iş günü getirisi (ortalama) ve modelin o rejimde verdiği çarpan. Çarpan < 1 (azalt) iken getiri güçlü pozitifse, rejim kuralı **dipte satıyor** demektir.

| Rejim | Başlangıç sayısı | Altın 60g (çarpan) | Gümüş 60g (çarpan) | Nasdaq 100 60g (çarpan) | S&P 500 60g (çarpan) | Kripto 60g (çarpan) | Ham Petrol 60g (çarpan) | Bakır 60g (çarpan) | ABD Tahvili / Faiz 60g (çarpan) |
|---|---|---|---|---|---|---|---|---|---|
| 1: Küresel Enflasyon & Stagflasyon Şoku | 31 | %-0.1 (1.25x) | %+0.9 (1.10x) | %+5.0 (0.40x) | %+3.6 (0.45x) | %+3.6 (0.35x) | %+6.1 (1.35x) | %+0.7 (0.85x) | %-3.1 (0.30x) |
| 2: Sistemik Likidite Şoku & Carry Çöküşü | 28 | %+2.5 (0.80x) | %+2.9 (0.60x) | %+6.2 (0.25x) | %+4.4 (0.30x) | %+7.1 (0.20x) | %+4.1 (0.50x) | %-1.1 (0.50x) | %-2.9 (0.70x) |
| 3: Reel Faiz Şoku | 27 | %+2.1 (0.65x) | %+4.4 (0.60x) | %+6.1 (0.35x) | %+4.6 (0.50x) | %+8.8 (0.35x) | %+3.1 (0.80x) | %+0.2 (0.75x) | %-0.1 (0.30x) |
| 4: Kredi Temerrüt Baskısı | 1 | %+8.3 (1.15x) | %+23.8 (0.85x) | %+29.7 (0.35x) | %+21.7 (0.35x) | %+27.7 (0.25x) | %+5.7 (0.60x) | %+15.6 (0.55x) | %-5.9 (1.20x) |
| 5: Küresel Likidite Rallisi (Risk-On) | 2 | %+4.3 (0.90x) | %+3.5 (1.05x) | %+9.0 (1.40x) | %+9.7 (1.35x) | %+51.5 (1.30x) | %+12.5 (0.90x) | %+3.0 (1.10x) | %-5.0 (1.10x) |
| Koşulsuz (tüm günler) | — | %+2.0 | %+2.4 | %+4.2 | %+2.9 | %+18.9 | %+2.1 | %+1.3 | %-0.0 |

## 5) Portföy testi — hedef ağırlıklar vs eşit ağırlık (örneklem dışı, işlem ertesi gün)

- **🎯 Min-DD rejim portföyü (yeni hedef, her çeyrek yalnızca geçmiş veriyle yeniden optimize):** yıllık getiri %+5.7 · volatilite %6.6 · Sharpe 0.87 · maks. düşüş %-15.9
- **🎯 Min-DD rejim portföyü — %100 yatırımda (nakitsiz):** yıllık getiri %+11.4 · volatilite %15.4 · Sharpe 0.74 · maks. düşüş %-38.9
- **Eski hedef (sinyal × rejim çarpanı + nakit):** yıllık getiri %+9.8 · volatilite %9.1 · Sharpe 1.08 · maks. düşüş %-22.4
- **Eşit ağırlık 8 varlık (%100 yatırımda):** yıllık getiri %+13.8 · volatilite %20.9 · Sharpe 0.66 · maks. düşüş %-57.6
- Ortalama nakit payı: %56. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)

## 6) Faktör bazında IC — her makro gösterge her varlıkta doğru yönde mi?
Değer = (gösterge z-skoru × modeldeki varlık kutbu) ile sonraki 60 iş günü getirisinin sıra korelasyonu. **Pozitif** = gösterge o varlığı doğru yöne itiyor; **negatif** = ters itiyor. ± işaretli değerlerde |t| ≥ 2 (anlamlı) olanlar **kalın**.

| Gösterge | ABD Tahvili / Faiz | Altın | Bakır | Gümüş | Ham Petrol | Kripto | Nasdaq 100 | S&P 500 |
|---|---|---|---|---|---|---|---|---|
| Dolar Endeksi Zayıflığı (DXY) | -0.11 | -0.17 | +0.10 | +0.00 | +0.27 | +0.23 | +0.25 | +0.27 |
| G4 Küresel Süper Likidite (Fed+ECB+BoJ) | +0.06 | -0.09 | +0.21 | -0.01 | +0.29 | **+0.33** | **+0.31** | +0.29 |
| Reel Faiz Seviyesi / Tahvil Taşıma Getirisi (TLT değerleme) | +0.10 | — | — | — | — | — | — | — |
| Reel Faiz İndirgeme İvmesi (10Y TIPS) | +0.00 | +0.05 | +0.10 | +0.05 | +0.11 | **+0.31** | +0.18 | +0.21 |
| 10Y Breakeven Enflasyon İvmesi | +0.14 | -0.07 | -0.22 | -0.14 | -0.20 | **-0.37** | +0.27 | +0.23 |
| 5Y5Y İleri Enflasyon Beklentisi (T5YIFR) | +0.08 | +0.02 | -0.25 | -0.04 | -0.24 | — | +0.21 | +0.17 |
| Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y) | +0.13 | +0.19 | +0.10 | +0.24 | +0.02 | **+0.36** | +0.22 | +0.23 |
| Yüksek Getirili Kredi Stresi (HY OAS) | +0.03 | **-0.32** | +0.10 | +0.18 | -0.11 | -0.13 | -0.05 | +0.00 |
| MOVE Endeksi (Tahvil Volatilitesi) | +0.15 | +0.15 | +0.11 | -0.13 | +0.21 | +0.16 | -0.04 | -0.02 |
| VIX Endeksi (Hisse Volatilitesi) | +0.16 | -0.16 | -0.19 | -0.10 | -0.14 | +0.11 | -0.17 | -0.23 |
| Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y) | -0.17 | -0.26 | +0.29 | +0.26 | +0.11 | +0.26 | +0.30 | **+0.34** |
| Öncü İstihdam (ICSA) | **-0.34** | -0.09 | -0.23 | -0.05 | -0.25 | +0.08 | -0.02 | -0.11 |
| Hazine Nakit / Banka Rezervleri (WRESBAL) | **-0.35** | -0.17 | +0.11 | -0.04 | +0.14 | +0.08 | -0.04 | +0.03 |

## 8) UZUN VADELİ DÖNGÜ SİNYALİ (dipten al-unut / tepeden sat-unut) — varlık bazında örneklem dışı
Her yıl yalnızca geçmiş veriyle en iyi parametre seçilir (3y/2y değer ortalaması, dip/tepe bant genişliği, dönüş teyidi, yeniden giriş kuralı) ve ERTESİ YIL uygulanır. Satış = nakde geç (kaldıraç/açığa satış yok). Karşılaştırma aynı dönemde al-tut ile.

| Varlık | Döngü yıllık | Döngü maks. DD | Al-tut yıllık | Al-tut maks. DD | Kârlı al-sat turu | SAT sonrası 120g düşüş isabeti | Piyasada kalma | Canlı parametre |
|---|---|---|---|---|---|---|---|---|
| Altın (XAU) | %+3.0 | %-10.2 | %+12.3 | %-24.9 | %100 (3) | %67 (3) | %12 | L=504, bant 20/80, teyit=yok, giriş=mean |
| Gümüş (XAG) | %+6.4 | %-19.9 | %+13.3 | %-51.4 | %100 (3) | %0 (3) | %18 | L=504, bant 10/90, teyit=yok, giriş=mean |
| Nasdaq 100 (NQ) | %+14.8 | %-22.9 | %+17.9 | %-35.6 | %100 (3) | %0 (4) | %70 | L=756, bant 10/90, teyit=yok, giriş=bottom |
| S&P 500 (SPX) | %+7.1 | %-34.1 | %+12.0 | %-34.1 | %100 (3) | %0 (4) | %61 | L=504, bant 15/85, teyit=var, giriş=bottom |
| Kripto (BTC) | %+42.6 | %-59.9 | %+33.8 | %-76.6 | %100 (1) | %0 (1) | %86 | L=756, bant 20/80, teyit=yok, giriş=bottom |
| Ham Petrol (WTI) | %+5.0 | %-47.2 | %+6.3 | %-86.9 | %33 (3) | %33 (4) | %29 | L=756, bant 10/90, teyit=var, giriş=mean |
| Bakır (HG) | %+5.6 | %-23.1 | %+9.4 | %-35.6 | %100 (2) | %33 (3) | %37 | L=756, bant 10/90, teyit=yok, giriş=mean |

## 7) PORTFÖY STRATEJİSİ YARIŞI (örneklem dışı) — canlı hedef buradan seçilir
Öncelik = minimum düşüş: maks. düşüşü %12 içinde kalanlar arasından en yüksek yıllık getirili strateji canlıya alınır (hiçbiri sığmazsa en küçük düşüşlü). Döngü stratejisi, varlık döngü sinyallerinin ÖRNEKLEM DIŞI hâlini kullanır. Haftalık dengeleme, ertesi gün işlem, 5 bps maliyet, kaldıraç yok.

| Strateji | Yıllık getiri | Maks. düşüş | Calmar | Sharpe | Kazançlı ay oranı | Kazançlı yıl oranı |
|---|---|---|---|---|---|---|
| Risk paritesi · %10 vol hedefi | %+10.2 | %-20.5 | 0.50 | 1.03 | %64 | %82 |
| Risk paritesi + 200g trend · %10 vol hedefi 🏆 **CANLI SEÇİM** | %+9.9 | %-11.2 | 0.88 | 1.26 | %64 | %82 |
| Risk paritesi · rejime göre vol hedefi | %+9.8 | %-16.3 | 0.60 | 1.10 | %63 | %82 |
| Risk paritesi + 200g trend · rejime göre vol hedefi | %+9.4 | %-10.3 | 0.91 | 1.26 | %64 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · %10 vol hedefi | %+8.6 | %-8.4 | 1.02 | 1.43 | %64 | %73 |
| Risk paritesi + 200g trend · rejime göre vol + düşüş freni | %+8.4 | %-9.1 | 0.93 | 1.19 | %60 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol hedefi | %+8.3 | %-8.2 | 1.01 | 1.47 | %63 | %73 |
| Risk paritesi · rejime göre vol + düşüş freni | %+7.3 | %-11.0 | 0.66 | 0.98 | %63 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol + düşüş freni | %+7.3 | %-7.6 | 0.96 | 1.36 | %63 | %73 |
| Eşit ağırlık 8 varlık (referans) | %+13.9 | %-57.8 | 0.24 | 0.66 | %66 | %73 |

## Sınırlar
- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).
- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.
- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok.
