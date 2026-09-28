# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama

_Oluşturma: 2026-09-28T08:20:52.451414+00:00 · dönem: 2016-09-28 → 2026-09-23 · 5 iş gününde bir değerlendirme_

Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.

## 1) TEPE / DİP TESTİ — sistem "dipten al, tepeden sat" yapıyor mu?
Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı (zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).

| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |
|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | +0.71 | +61.4 (n=30) | -38.8 (n=81) | %+1.8 | %+1.8 |
| Altın (XAU) | +0.34 | +29.0 (n=126) | -38.2 (n=19) | %+5.8 | %+4.0 |
| Bakır (HG) | +0.63 | +44.4 (n=102) | -43.8 (n=20) | %+3.6 | %+4.5 |
| Gümüş (XAG) | +0.54 | +46.5 (n=59) | -40.3 (n=33) | %+11.6 | %+5.1 |
| Ham Petrol (WTI) | +0.37 | +41.6 (n=92) | -20.3 (n=40) | %+3.1 | %+15.0 |
| Kripto (BTC) | +0.72 | +38.9 (n=119) | -55.3 (n=72) | %+35.1 | %+4.6 |
| Nasdaq 100 (NQ) | +0.62 | +32.7 (n=288) | -64.6 (n=17) | %+3.3 | %+7.4 |
| S&P 500 (SPX) | +0.62 | +38.7 (n=290) | -71.9 (n=11) | %+2.2 | %+9.8 |

## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?
IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. |t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).

| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |
|---|---|---|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | **TOPLAM SKOR** | +0.056 | +0.102 | +0.131 | +0.7 | 510 |
| ABD Tahvili / Faiz (TLT) | makro | +0.020 | +0.063 | +0.114 | +0.4 | 510 |
| ABD Tahvili / Faiz (TLT) | piyasa (trend+zirve yakınlığı) | +0.021 | +0.002 | -0.020 | +0.0 | 510 |
| ABD Tahvili / Faiz (TLT) | risk döngüsü | -0.001 | -0.017 | -0.049 | -0.1 | 510 |
| Altın (XAU) | **TOPLAM SKOR** | -0.114 | -0.253 | -0.272 | -1.7 | 510 |
| Altın (XAU) | makro | -0.188 | -0.371 | -0.432 | -2.4 | 510 |
| Altın (XAU) | piyasa (trend+zirve yakınlığı) | +0.017 | +0.004 | +0.043 | +0.0 | 510 |
| Altın (XAU) | risk döngüsü | +0.023 | -0.096 | -0.145 | -0.6 | 510 |
| Bakır (HG) | **TOPLAM SKOR** | -0.125 | -0.139 | -0.025 | -0.9 | 510 |
| Bakır (HG) | makro | -0.105 | -0.110 | -0.006 | -0.7 | 510 |
| Bakır (HG) | piyasa (trend+zirve yakınlığı) | -0.079 | -0.068 | -0.067 | -0.4 | 510 |
| Bakır (HG) | risk döngüsü | +0.062 | +0.072 | +0.140 | +0.5 | 510 |
| Gümüş (XAG) | **TOPLAM SKOR** | -0.079 | -0.122 | -0.161 | -0.8 | 510 |
| Gümüş (XAG) | makro | -0.110 | -0.186 | -0.284 | -1.2 | 510 |
| Gümüş (XAG) | piyasa (trend+zirve yakınlığı) | -0.044 | -0.038 | +0.014 | -0.2 | 510 |
| Gümüş (XAG) | risk döngüsü | +0.017 | +0.071 | +0.158 | +0.5 | 510 |
| Ham Petrol (WTI) | **TOPLAM SKOR** | -0.041 | -0.036 | +0.032 | -0.2 | 510 |
| Ham Petrol (WTI) | makro | -0.039 | +0.016 | +0.098 | +0.1 | 510 |
| Ham Petrol (WTI) | piyasa (trend+zirve yakınlığı) | -0.009 | -0.111 | -0.105 | -0.7 | 510 |
| Ham Petrol (WTI) | risk döngüsü | +0.115 | +0.077 | +0.015 | +0.5 | 510 |
| Kripto (BTC) | **TOPLAM SKOR** | +0.215 | +0.327 | +0.247 | +2.1 | 510 |
| Kripto (BTC) | makro | +0.200 | +0.312 | +0.217 | +2.0 | 510 |
| Kripto (BTC) | piyasa (trend+zirve yakınlığı) | +0.152 | +0.254 | +0.254 | +1.7 | 510 |
| Kripto (BTC) | risk döngüsü | +0.127 | +0.255 | +0.264 | +1.7 | 510 |
| Nasdaq 100 (NQ) | **TOPLAM SKOR** | +0.077 | +0.064 | +0.039 | +0.4 | 510 |
| Nasdaq 100 (NQ) | makro | +0.144 | +0.182 | +0.167 | +1.2 | 510 |
| Nasdaq 100 (NQ) | piyasa (trend+zirve yakınlığı) | -0.085 | -0.158 | -0.116 | -1.0 | 510 |
| Nasdaq 100 (NQ) | risk döngüsü | +0.067 | +0.051 | +0.096 | +0.3 | 510 |
| S&P 500 (SPX) | **TOPLAM SKOR** | +0.030 | +0.068 | +0.034 | +0.4 | 510 |
| S&P 500 (SPX) | makro | +0.073 | +0.150 | +0.131 | +1.0 | 510 |
| S&P 500 (SPX) | piyasa (trend+zirve yakınlığı) | -0.116 | -0.149 | -0.141 | -1.0 | 510 |
| S&P 500 (SPX) | risk döngüsü | +0.041 | +0.070 | +0.093 | +0.5 | 510 |

## 3) Etiket isabeti (60 gün sonrası)

| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |
|---|---|---|---|
| ABD Tahvili / Faiz (TLT) | %51 · %-0.1 (275) | %53 · %-1.1 (131) | %44 · %-0.8 |
| Altın (XAU) | %54 · %+1.5 (262) | %36 · %+3.2 (90) | %65 · %+3.3 |
| Bakır (HG) | %55 · %+2.9 (268) | %34 · %+5.6 (62) | %59 · %+2.9 |
| Gümüş (XAG) | %56 · %+3.9 (253) | %32 · %+6.1 (103) | %57 · %+4.3 |
| Ham Petrol (WTI) | %55 · %+3.7 (287) | %40 · %+11.8 (95) | %53 · %+3.9 |
| Kripto (BTC) | %60 · %+25.8 (286) | %61 · %-0.9 (173) | %59 · %+20.5 |
| Nasdaq 100 (NQ) | %78 · %+4.9 (313) | %41 · %+3.3 (115) | %74 · %+4.7 |
| S&P 500 (SPX) | %79 · %+3.2 (336) | %41 · %+3.0 (91) | %76 · %+3.2 |

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

## 5) Portföy testi — modelin hedef ağırlıkları vs eşit ağırlık

- **Model (hedef ağırlıklar + nakit):** yıllık getiri %+9.7 · volatilite %8.3 · Sharpe 1.17 · maks. düşüş %-17.8
- **Eşit ağırlık 8 varlık (%100 yatırımda):** yıllık getiri %+13.8 · volatilite %20.9 · Sharpe 0.66 · maks. düşüş %-57.6
- Ortalama nakit payı: %56. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)

## Sınırlar
- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).
- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.
- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok.
