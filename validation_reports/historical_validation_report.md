# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama

_Oluşturma: 2026-10-11T11:31:50.545108+00:00 · dönem: 2016-10-12 → 2026-10-07 · 5 iş gününde bir değerlendirme_

Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.

## 1) TEPE / DİP TESTİ — sistem "dipten al, tepeden sat" yapıyor mu?
Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı (zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).

| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |
|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | +0.50 | +29.4 (n=30) | -38.4 (n=83) | %+1.8 | %+1.8 |
| Altın (XAU) | +0.37 | +6.0 (n=126) | -44.6 (n=19) | %+5.8 | %+4.0 |
| Bakır (HG) | +0.41 | +14.5 (n=102) | -40.0 (n=20) | %+3.6 | %+4.5 |
| Gümüş (XAG) | +0.54 | +19.8 (n=59) | -38.9 (n=33) | %+11.6 | %+5.1 |
| Ham Petrol (WTI) | +0.06 | +9.6 (n=91) | -11.9 (n=40) | %+3.1 | %+15.0 |
| Kripto (BTC) | +0.50 | +20.8 (n=119) | -28.2 (n=72) | %+35.1 | %+5.1 |
| Nasdaq 100 (NQ) | +0.50 | +8.9 (n=288) | -49.9 (n=17) | %+3.3 | %+7.4 |
| S&P 500 (SPX) | +0.54 | +10.1 (n=289) | -68.9 (n=11) | %+2.2 | %+9.8 |

## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?
IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. |t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).

| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |
|---|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | **TOPLAM SKOR** | +0.094 | +0.104 | +0.098 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | makro | +0.074 | +0.115 | +0.160 | +0.8 | 510 |
| ABD Tahvili / Faiz (TLT) | piyasa (trend+zirve yakınlığı) | +0.057 | +0.053 | +0.000 | +0.3 | 510 |
| ABD Tahvili / Faiz (TLT) | risk döngüsü | -0.008 | -0.017 | -0.050 | -0.1 | 510 |
| Altın (XAU) | **TOPLAM SKOR** | -0.058 | -0.140 | -0.077 | -0.9 | 510 |
| Altın (XAU) | makro | -0.100 | -0.169 | -0.096 | -1.1 | 510 |
| Altın (XAU) | piyasa (trend+zirve yakınlığı) | +0.007 | -0.031 | -0.003 | -0.2 | 510 |
| Altın (XAU) | risk döngüsü | +0.023 | -0.098 | -0.133 | -0.6 | 510 |
| Bakır (HG) | **TOPLAM SKOR** | -0.084 | -0.097 | +0.014 | -0.6 | 510 |
| Bakır (HG) | makro | -0.094 | -0.091 | +0.020 | -0.6 | 510 |
| Bakır (HG) | piyasa (trend+zirve yakınlığı) | -0.027 | -0.001 | +0.007 | -0.0 | 510 |
| Bakır (HG) | risk döngüsü | +0.062 | +0.073 | +0.140 | +0.5 | 510 |
| Gümüş (XAG) | **TOPLAM SKOR** | -0.060 | -0.077 | -0.047 | -0.5 | 510 |
| Gümüş (XAG) | makro | -0.065 | -0.073 | -0.081 | -0.5 | 510 |
| Gümüş (XAG) | piyasa (trend+zirve yakınlığı) | -0.023 | -0.040 | -0.005 | -0.3 | 510 |
| Gümüş (XAG) | risk döngüsü | +0.017 | +0.073 | +0.146 | +0.5 | 510 |
| Ham Petrol (WTI) | **TOPLAM SKOR** | +0.014 | +0.035 | +0.115 | +0.2 | 510 |
| Ham Petrol (WTI) | makro | -0.040 | +0.023 | +0.116 | +0.2 | 510 |
| Ham Petrol (WTI) | piyasa (trend+zirve yakınlığı) | +0.056 | +0.021 | +0.028 | +0.1 | 510 |
| Ham Petrol (WTI) | risk döngüsü | +0.115 | +0.080 | +0.013 | +0.5 | 510 |
| Kripto (BTC) | **TOPLAM SKOR** | +0.250 | +0.389 | +0.302 | +2.5 | 510 |
| Kripto (BTC) | makro | +0.221 | +0.366 | +0.288 | +2.4 | 510 |
| Kripto (BTC) | piyasa (trend+zirve yakınlığı) | +0.059 | +0.079 | +0.047 | +0.5 | 510 |
| Kripto (BTC) | risk döngüsü | +0.127 | +0.256 | +0.260 | +1.7 | 510 |
| Nasdaq 100 (NQ) | **TOPLAM SKOR** | +0.102 | +0.132 | +0.167 | +0.9 | 510 |
| Nasdaq 100 (NQ) | makro | +0.151 | +0.220 | +0.230 | +1.4 | 510 |
| Nasdaq 100 (NQ) | piyasa (trend+zirve yakınlığı) | -0.060 | -0.126 | -0.048 | -0.8 | 510 |
| Nasdaq 100 (NQ) | risk döngüsü | +0.068 | +0.050 | +0.099 | +0.3 | 510 |
| S&P 500 (SPX) | **TOPLAM SKOR** | +0.030 | +0.079 | +0.101 | +0.5 | 510 |
| S&P 500 (SPX) | makro | +0.058 | +0.141 | +0.157 | +0.9 | 510 |
| S&P 500 (SPX) | piyasa (trend+zirve yakınlığı) | -0.059 | -0.092 | -0.073 | -0.6 | 510 |
| S&P 500 (SPX) | risk döngüsü | +0.041 | +0.068 | +0.094 | +0.4 | 510 |

## 3) Etiket isabeti (60 gün sonrası)

| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |
|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | %41 · %-1.0 (209) | %60 · %-1.7 (141) | %44 · %-0.8 |
| Altın (XAU) | %61 · %+2.9 (179) | %34 · %+3.4 (150) | %65 · %+3.3 |
| Bakır (HG) | %60 · %+4.0 (113) | %37 · %+3.6 (65) | %59 · %+2.9 |
| Gümüş (XAG) | %65 · %+5.8 (144) | %31 · %+5.2 (103) | %57 · %+4.4 |
| Ham Petrol (WTI) | %54 · %+6.9 (152) | %45 · %+11.2 (69) | %53 · %+3.9 |
| Kripto (BTC) | %64 · %+31.5 (223) | %59 · %-1.2 (113) | %59 · %+20.4 |
| Nasdaq 100 (NQ) | %70 · %+3.7 (195) | %42 · %+2.3 (137) | %74 · %+4.7 |
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

- **🎯 Min-DD rejim portföyü (yeni hedef, her çeyrek yalnızca geçmiş veriyle yeniden optimize):** yıllık getiri %+5.6 · volatilite %6.5 · Sharpe 0.87 · maks. düşüş %-16.2
- **🎯 Min-DD rejim portföyü — %100 yatırımda (nakitsiz):** yıllık getiri %+10.8 · volatilite %15.3 · Sharpe 0.70 · maks. düşüş %-40.8
- **Eski hedef (sinyal × rejim çarpanı + nakit):** yıllık getiri %+9.8 · volatilite %9.1 · Sharpe 1.07 · maks. düşüş %-22.4
- **Eşit ağırlık 8 varlık (%100 yatırımda):** yıllık getiri %+13.9 · volatilite %20.9 · Sharpe 0.66 · maks. düşüş %-57.6
- Ortalama nakit payı: %56. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)

## 6) Faktör bazında IC — her makro gösterge her varlıkta doğru yönde mi?
Değer = (gösterge z-skoru × modeldeki varlık kutbu) ile sonraki 60 iş günü getirisinin sıra korelasyonu. **Pozitif** = gösterge o varlığı doğru yöne itiyor; **negatif** = ters itiyor. ± işaretli değerlerde |t| ≥ 2 (anlamlı) olanlar **kalın**.

| Gösterge | ABD Tahvili / Faiz | Altın | Bakır | Gümüş | Ham Petrol | Kripto | Nasdaq 100 | S&P 500 |
|---|---|---|---|---|---|---|---|---|
| Dolar Endeksi Zayıflığı (DXY) | -0.10 | -0.17 | +0.10 | +0.00 | +0.26 | +0.23 | +0.25 | +0.28 |
| G4 Küresel Süper Likidite (Fed+ECB+BoJ) | +0.06 | -0.09 | +0.21 | -0.01 | +0.29 | **+0.33** | **+0.31** | +0.30 |
| Reel Faiz Seviyesi / Tahvil Taşıma Getirisi (TLT değerleme) | +0.09 | — | — | — | — | — | — | — |
| Reel Faiz İndirgeme İvmesi (10Y TIPS) | +0.01 | +0.05 | +0.10 | +0.05 | +0.11 | +0.31 | +0.18 | +0.21 |
| 10Y Breakeven Enflasyon İvmesi | +0.15 | -0.08 | -0.21 | -0.15 | -0.20 | **-0.37** | +0.28 | +0.23 |
| 5Y5Y İleri Enflasyon Beklentisi (T5YIFR) | +0.09 | +0.01 | -0.24 | -0.05 | -0.24 | — | +0.21 | +0.17 |
| Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y) | +0.15 | +0.20 | +0.10 | +0.24 | +0.01 | **+0.35** | +0.22 | +0.23 |
| Yüksek Getirili Kredi Stresi (HY OAS) | +0.05 | **-0.31** | +0.09 | +0.17 | -0.10 | -0.13 | -0.07 | -0.02 |
| MOVE Endeksi (Tahvil Volatilitesi) | +0.15 | +0.15 | +0.11 | -0.12 | +0.21 | +0.16 | -0.04 | -0.02 |
| VIX Endeksi (Hisse Volatilitesi) | +0.17 | -0.17 | -0.19 | -0.10 | -0.14 | +0.11 | -0.17 | -0.23 |
| Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y) | -0.18 | -0.25 | +0.29 | +0.26 | +0.10 | +0.25 | +0.29 | **+0.35** |
| Öncü İstihdam (ICSA) | **-0.35** | -0.10 | -0.24 | -0.04 | -0.26 | +0.07 | -0.01 | -0.11 |
| Hazine Nakit / Banka Rezervleri (WRESBAL) | **-0.35** | -0.17 | +0.11 | -0.04 | +0.13 | +0.07 | -0.04 | +0.03 |

## 8) UZUN VADELİ DÖNGÜ SİNYALİ (dipten al-unut / tepeden sat-unut) — varlık bazında örneklem dışı
Her yıl yalnızca geçmiş veriyle en iyi parametre seçilir (3y/2y değer ortalaması, dip/tepe bant genişliği, dönüş teyidi, yeniden giriş kuralı) ve ERTESİ YIL uygulanır. Satış = nakde geç (kaldıraç/açığa satış yok). Karşılaştırma aynı dönemde al-tut ile.

| Varlık | Döngü yıllık | Döngü maks. DD | Al-tut yıllık | Al-tut maks. DD | Kârlı al-sat turu | SAT sonrası 120g düşüş isabeti | Piyasada kalma | Canlı parametre |
|---|---|---|---|---|---|---|---|---|
| Altın (XAU) | %+2.4 | %-10.2 | %+12.4 | %-24.9 | %75 (4) | %50 (4) | %14 | L=504, bant 20/80, teyit=yok, giriş=mean |
| Gümüş (XAG) | %+6.3 | %-19.9 | %+13.0 | %-51.4 | %100 (3) | %0 (3) | %18 | L=504, bant 10/90, teyit=yok, giriş=mean |
| Nasdaq 100 (NQ) | %+14.0 | %-23.0 | %+18.0 | %-35.6 | %75 (4) | %20 (5) | %62 | L=756, bant 10/90, teyit=yok, giriş=bottom |
| S&P 500 (SPX) | %+7.1 | %-34.1 | %+12.1 | %-34.1 | %100 (3) | %0 (4) | %61 | L=504, bant 15/85, teyit=var, giriş=bottom |
| Kripto (BTC) | %+42.4 | %-59.9 | %+33.6 | %-76.6 | %100 (1) | %0 (1) | %86 | L=756, bant 20/80, teyit=yok, giriş=bottom |
| Ham Petrol (WTI) | %+5.9 | %-47.2 | %+6.6 | %-86.9 | %33 (3) | %0 (4) | %31 | L=756, bant 10/90, teyit=var, giriş=mean |
| Bakır (HG) | %+3.7 | %-23.1 | %+9.5 | %-35.6 | %100 (2) | %0 (3) | %34 | L=756, bant 10/90, teyit=yok, giriş=mean |

## 7) PORTFÖY STRATEJİSİ YARIŞI (örneklem dışı) — canlı hedef buradan seçilir
Öncelik = minimum düşüş: maks. düşüşü %12 içinde kalanlar arasından en yüksek yıllık getirili strateji canlıya alınır (hiçbiri sığmazsa en küçük düşüşlü). Döngü stratejisi, varlık döngü sinyallerinin ÖRNEKLEM DIŞI hâlini kullanır. Haftalık dengeleme, ertesi gün işlem, 5 bps maliyet, kaldıraç yok.

| Strateji | Yıllık getiri | Maks. düşüş | Calmar | Sharpe | Kazançlı ay oranı | Kazançlı yıl oranı |
|---|---|---|---|---|---|---|
| Risk paritesi · %10 vol hedefi | %+10.3 | %-20.5 | 0.50 | 1.04 | %64 | %82 |
| Risk paritesi + 200g trend · %10 vol hedefi 🏆 **CANLI SEÇİM** | %+10.1 | %-11.2 | 0.90 | 1.29 | %64 | %82 |
| Risk paritesi · rejime göre vol hedefi | %+9.9 | %-16.3 | 0.61 | 1.12 | %64 | %82 |
| Risk paritesi + 200g trend · rejime göre vol hedefi | %+9.6 | %-10.3 | 0.93 | 1.29 | %64 | %82 |
| Risk paritesi + 200g trend · rejime göre vol + düşüş freni | %+8.7 | %-9.1 | 0.96 | 1.22 | %60 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · %10 vol hedefi | %+8.0 | %-8.2 | 0.97 | 1.35 | %64 | %73 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol hedefi | %+7.8 | %-7.9 | 0.98 | 1.39 | %64 | %73 |
| Risk paritesi · rejime göre vol + düşüş freni | %+7.3 | %-11.0 | 0.66 | 0.99 | %64 | %82 |
| Döngü (dipten al / tepeden sat) + risk paritesi · rejime göre vol + düşüş freni | %+6.8 | %-7.3 | 0.94 | 1.28 | %64 | %73 |
| Eşit ağırlık 8 varlık (referans) | %+13.9 | %-57.8 | 0.24 | 0.66 | %66 | %73 |

## Sınırlar
- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).
- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.
- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok.
