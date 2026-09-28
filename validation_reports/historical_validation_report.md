# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama

_Oluşturma: 2026-09-28T09:50:05.018608+00:00 · dönem: 2016-09-28 → 2026-09-23 · 5 iş gününde bir değerlendirme_

Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.

## 1) TEPE / DİP TESTİ — sistem "dipten al, tepeden sat" yapıyor mu?
Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı (zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).

| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |
|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | +0.50 | +29.3 (n=30) | -39.5 (n=81) | %+1.8 | %+1.8 |
| Altın (XAU) | +0.35 | +6.2 (n=126) | -43.1 (n=19) | %+5.8 | %+4.0 |
| Bakır (HG) | +0.41 | +14.6 (n=102) | -38.7 (n=20) | %+3.6 | %+4.5 |
| Gümüş (XAG) | +0.51 | +19.7 (n=59) | -36.6 (n=33) | %+11.6 | %+5.1 |
| Ham Petrol (WTI) | +0.10 | +12.6 (n=92) | -11.5 (n=40) | %+3.1 | %+15.0 |
| Kripto (BTC) | +0.49 | +19.9 (n=119) | -27.7 (n=72) | %+35.1 | %+4.6 |
| Nasdaq 100 (NQ) | +0.50 | +8.9 (n=288) | -49.8 (n=17) | %+3.3 | %+7.4 |
| S&P 500 (SPX) | +0.54 | +9.9 (n=290) | -68.8 (n=11) | %+2.2 | %+9.8 |

## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?
IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. |t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).

| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |
|---|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | **TOPLAM SKOR** | +0.092 | +0.097 | +0.091 | +0.6 | 510 |
| ABD Tahvili / Faiz (TLT) | makro | +0.068 | +0.102 | +0.147 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | piyasa (trend+zirve yakınlığı) | +0.056 | +0.055 | +0.006 | +0.4 | 510 |
| ABD Tahvili / Faiz (TLT) | risk döngüsü | -0.001 | -0.017 | -0.049 | -0.1 | 510 |
| Altın (XAU) | **TOPLAM SKOR** | -0.069 | -0.144 | -0.094 | -0.9 | 510 |
| Altın (XAU) | makro | -0.124 | -0.186 | -0.124 | -1.2 | 510 |
| Altın (XAU) | piyasa (trend+zirve yakınlığı) | +0.007 | -0.022 | -0.004 | -0.1 | 510 |
| Altın (XAU) | risk döngüsü | +0.023 | -0.096 | -0.145 | -0.6 | 510 |
| Bakır (HG) | **TOPLAM SKOR** | -0.098 | -0.116 | -0.007 | -0.8 | 510 |
| Bakır (HG) | makro | -0.109 | -0.118 | -0.009 | -0.8 | 510 |
| Bakır (HG) | piyasa (trend+zirve yakınlığı) | -0.028 | +0.004 | +0.010 | +0.0 | 510 |
| Bakır (HG) | risk döngüsü | +0.062 | +0.072 | +0.140 | +0.5 | 510 |
| Gümüş (XAG) | **TOPLAM SKOR** | -0.070 | -0.084 | -0.063 | -0.6 | 510 |
| Gümüş (XAG) | makro | -0.084 | -0.088 | -0.109 | -0.6 | 510 |
| Gümüş (XAG) | piyasa (trend+zirve yakınlığı) | -0.017 | -0.031 | +0.000 | -0.2 | 510 |
| Gümüş (XAG) | risk döngüsü | +0.017 | +0.071 | +0.158 | +0.5 | 510 |
| Ham Petrol (WTI) | **TOPLAM SKOR** | +0.010 | +0.022 | +0.096 | +0.1 | 510 |
| Ham Petrol (WTI) | makro | -0.044 | +0.007 | +0.091 | +0.0 | 510 |
| Ham Petrol (WTI) | piyasa (trend+zirve yakınlığı) | +0.059 | +0.021 | +0.028 | +0.1 | 510 |
| Ham Petrol (WTI) | risk döngüsü | +0.115 | +0.077 | +0.015 | +0.5 | 510 |
| Kripto (BTC) | **TOPLAM SKOR** | +0.244 | +0.377 | +0.281 | +2.5 | 510 |
| Kripto (BTC) | makro | +0.216 | +0.353 | +0.263 | +2.3 | 510 |
| Kripto (BTC) | piyasa (trend+zirve yakınlığı) | +0.053 | +0.071 | +0.044 | +0.5 | 510 |
| Kripto (BTC) | risk döngüsü | +0.127 | +0.255 | +0.264 | +1.7 | 510 |
| Nasdaq 100 (NQ) | **TOPLAM SKOR** | +0.107 | +0.132 | +0.169 | +0.9 | 510 |
| Nasdaq 100 (NQ) | makro | +0.155 | +0.220 | +0.234 | +1.4 | 510 |
| Nasdaq 100 (NQ) | piyasa (trend+zirve yakınlığı) | -0.056 | -0.127 | -0.053 | -0.8 | 510 |
| Nasdaq 100 (NQ) | risk döngüsü | +0.067 | +0.051 | +0.096 | +0.3 | 510 |
| S&P 500 (SPX) | **TOPLAM SKOR** | +0.031 | +0.082 | +0.102 | +0.5 | 510 |
| S&P 500 (SPX) | makro | +0.053 | +0.143 | +0.159 | +0.9 | 510 |
| S&P 500 (SPX) | piyasa (trend+zirve yakınlığı) | -0.056 | -0.092 | -0.077 | -0.6 | 510 |
| S&P 500 (SPX) | risk döngüsü | +0.041 | +0.070 | +0.093 | +0.5 | 510 |

## 3) Etiket isabeti (60 gün sonrası)

| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |
|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | %41 · %-1.1 (212) | %58 · %-1.7 (149) | %44 · %-0.8 |
| Altın (XAU) | %60 · %+2.7 (174) | %36 · %+3.2 (142) | %65 · %+3.3 |
| Bakır (HG) | %60 · %+4.2 (108) | %37 · %+4.0 (60) | %59 · %+2.9 |
| Gümüş (XAG) | %64 · %+5.8 (137) | %32 · %+5.3 (95) | %57 · %+4.3 |
| Ham Petrol (WTI) | %56 · %+7.2 (144) | %40 · %+13.5 (58) | %53 · %+3.9 |
| Kripto (BTC) | %64 · %+31.5 (221) | %59 · %-0.7 (112) | %59 · %+20.5 |
| Nasdaq 100 (NQ) | %70 · %+3.8 (192) | %42 · %+2.3 (136) | %74 · %+4.7 |
| S&P 500 (SPX) | %78 · %+3.4 (171) | %39 · %+2.7 (115) | %76 · %+3.2 |

## 4) Rejim başlangıcı sonrası getiriler — rejim çarpanları doğru yönde mi?
Her rejim ilk onaylandığında sonraki 60 iş günü getirisi (ortalama) ve modelin o rejimde verdiği çarpan. Çarpan < 1 (azalt) iken getiri güçlü pozitifse, rejim kuralı **dipte satıyor** demektir.

| Rejim | Başlangıç sayısı | Altın 60g (çarpan) | Gümüş 60g (çarpan) | Nasdaq 100 60g (çarpan) | S&P 500 60g (çarpan) | Kripto 60g (çarpan) | Ham Petrol 60g (çarpan) | Bakır 60g (çarpan) | ABD Tahvili / Faiz 60g (çarpan) |
|---|---|---|---|---|---|---|---|---|---|
| 1: Küresel Enflasyon & Stagflasyon Şoku | 27 | %-0.5 (1.25x) | %+0.3 (1.10x) | %+5.2 (0.40x) | %+3.4 (0.45x) | %+4.0 (0.35x) | %+8.7 (1.35x) | %+1.6 (0.85x) | %-3.9 (0.30x) |
| 2: Sistemik Likidite Şoku & Carry Çöküşü | 27 | %+2.5 (0.80x) | %+2.7 (0.60x) | %+6.5 (0.25x) | %+4.6 (0.30x) | %+9.3 (0.20x) | %+4.0 (0.50x) | %-0.3 (0.50x) | %-2.9 (0.70x) |
| 3: Reel Faiz Şoku | 18 | %+4.0 (0.65x) | %+8.9 (0.60x) | %+6.8 (0.35x) | %+5.8 (0.50x) | %+13.8 (0.35x) | %+10.4 (0.80x) | %+3.7 (0.75x) | %-1.8 (0.30x) |
| 4: Kredi Temerrüt Baskısı | 1 | %+8.3 (1.15x) | %+23.8 (0.85x) | %+29.7 (0.35x) | %+21.7 (0.35x) | %+27.7 (0.25x) | %+5.7 (0.60x) | %+15.6 (0.55x) | %-5.9 (1.20x) |
| 5: Küresel Likidite Rallisi (Risk-On) | 2 | %+4.3 (0.90x) | %+3.5 (1.05x) | %+9.0 (1.40x) | %+9.7 (1.35x) | %+51.5 (1.30x) | %+12.5 (0.90x) | %+3.0 (1.10x) | %-5.0 (1.10x) |
| Koşulsuz (tüm günler) | — | %+2.8 | %+3.7 | %+4.3 | %+2.9 | %+19.0 | %+2.7 | %+2.0 | %-0.5 |

## 5) Portföy testi — hedef ağırlıklar vs eşit ağırlık (örneklem dışı, işlem ertesi gün)

- **🎯 Min-DD rejim portföyü (yeni hedef, her çeyrek yalnızca geçmiş veriyle yeniden optimize):** yıllık getiri %+3.4 · volatilite %7.2 · Sharpe 0.46 · maks. düşüş %-22.0
- **🎯 Min-DD rejim portföyü — %100 yatırımda (nakitsiz):** yıllık getiri %+5.5 · volatilite %17.4 · Sharpe 0.32 · maks. düşüş %-51.0
- **Eski hedef (sinyal × rejim çarpanı + nakit):** yıllık getiri %+9.7 · volatilite %9.1 · Sharpe 1.07 · maks. düşüş %-22.4
- **Eşit ağırlık 8 varlık (%100 yatırımda):** yıllık getiri %+13.8 · volatilite %20.9 · Sharpe 0.66 · maks. düşüş %-57.6
- Ortalama nakit payı: %56. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)

## 6) Faktör bazında IC — her makro gösterge her varlıkta doğru yönde mi?
Değer = (gösterge z-skoru × modeldeki varlık kutbu) ile sonraki 60 iş günü getirisinin sıra korelasyonu. **Pozitif** = gösterge o varlığı doğru yöne itiyor; **negatif** = ters itiyor. ± işaretli değerlerde |t| ≥ 2 (anlamlı) olanlar **kalın**.

| Gösterge | ABD Tahvili / Faiz | Altın | Bakır | Gümüş | Ham Petrol | Kripto | Nasdaq 100 | S&P 500 |
|---|---|---|---|---|---|---|---|---|
| Dolar Endeksi Zayıflığı (DXY) | -0.11 | -0.17 | +0.10 | +0.00 | +0.27 | +0.23 | +0.25 | +0.27 |
| G4 Küresel Süper Likidite (Fed+ECB+BoJ) | +0.06 | -0.09 | +0.21 | -0.01 | +0.29 | **+0.33** | **+0.32** | +0.30 |
| Reel Faiz Seviyesi / Tahvil Taşıma Getirisi (TLT değerleme) | +0.10 | — | — | — | — | — | — | — |
| Reel Faiz İndirgeme İvmesi (10Y TIPS) | +0.00 | +0.05 | +0.10 | +0.05 | +0.11 | **+0.31** | +0.19 | +0.21 |
| 10Y Breakeven Enflasyon İvmesi | +0.12 | -0.12 | -0.26 | -0.18 | -0.21 | **-0.39** | +0.29 | +0.27 |
| 5Y5Y İleri Enflasyon Beklentisi (T5YIFR) | +0.03 | -0.03 | -0.30 | -0.09 | -0.27 | — | +0.21 | +0.21 |
| Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y) | +0.13 | +0.19 | +0.10 | +0.24 | +0.02 | **+0.36** | +0.22 | +0.23 |
| Yüksek Getirili Kredi Stresi (HY OAS) | +0.03 | **-0.32** | +0.10 | +0.18 | -0.11 | -0.13 | -0.05 | +0.00 |
| MOVE Endeksi (Tahvil Volatilitesi) | +0.15 | +0.15 | +0.11 | -0.13 | +0.21 | +0.18 | -0.04 | -0.02 |
| VIX Endeksi (Hisse Volatilitesi) | +0.16 | -0.16 | -0.19 | -0.10 | -0.14 | +0.11 | -0.17 | -0.23 |
| Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y) | -0.17 | -0.26 | +0.29 | +0.26 | +0.11 | +0.26 | +0.30 | **+0.34** |
| Öncü İstihdam (ICSA) | **-0.37** | -0.09 | -0.27 | -0.05 | -0.26 | +0.03 | -0.03 | -0.12 |
| Hazine Nakit / Banka Rezervleri (WRESBAL) | **-0.37** | -0.13 | +0.09 | +0.00 | +0.16 | -0.04 | -0.06 | +0.03 |

## 7) PORTFÖY STRATEJİSİ YARIŞI (örneklem dışı) — canlı hedef buradan seçilir
Her strateji her hafta YALNIZCA o güne kadarki veriyle ağırlık üretir, ertesi gün uygulanır (5 bps işlem maliyeti). Calmar = yıllık getiri / |maks. düşüş|. Canlı 🎯 Hedef Portföy sayfası **en yüksek Calmar**'a sahip stratejiyi kullanır.

| Strateji | Yıllık getiri | Volatilite | Sharpe | Maks. düşüş | Calmar | Ort. nakit |
|---|---|---|---|---|---|---|
| Risk paritesi + 200g trend filtresi + %10 vol hedefi 🏆 **CANLI SEÇİM** | %+9.2 | %7.9 | 1.17 | %-11.5 | 0.80 | %36 |
| Risk paritesi + %10 volatilite hedefi (düşeni alarak dengeler) | %+9.7 | %10.2 | 0.95 | %-21.9 | 0.44 | %11 |
| Rejim minimum drawdown + %10 vol hedefi | %+7.1 | %9.9 | 0.71 | %-22.3 | 0.32 | %10 |
| Rejim Calmar (rejimde maks. getiri, maks. DD ≤ %10) + vol hedefi | %+6.6 | %12.1 | 0.55 | %-35.3 | 0.19 | %25 |
| Eşit ağırlık 8 varlık (referans) | %+13.8 | %20.9 | 0.66 | %-57.6 | 0.24 | %0 |

## Sınırlar
- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).
- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.
- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok.
