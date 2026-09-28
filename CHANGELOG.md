# 2026-09-28 — v2.5: Canlı yenile butonu, ayrı "🎯 Hedef Portföy" sayfası (rejim bazlı minimum drawdown)

## 1) 🔄 Canlı Verileri Yenile
- Her iki sayfanın yan menüsünde. Tüm önbelleği (FRED, Yahoo, rejim motoru,
  portföy optimizasyonu) temizleyip her şeyi yeniden hesaplar. Altında son veri
  yükleme zamanı yazar. Otomatik yenileme de 15 dakikada bir sürer.
- Veri + motor katmanı `macro_pipeline.py`'ye taşındı: iki sayfa aynı önbelleği
  kullanır, ikinci sayfayı açmak hiçbir şeyi yeniden indirmez.
- FRED anahtarı Streamlit Secrets'ta yoksa uygulama artık durmuyor; anahtarsız
  halka açık FRED CSV'sine düşüyor.

## 2) 🎯 Hedef Portföy — ayrı sayfa, her rejim için minimum drawdown
- `pages/1_Hedef_Portfoy.py` + `regime_portfolio.py`.
- Her rejim (0-5) için, o rejimin onaylı olduğu tarihsel günlerde en küçük düşüşü
  yaşamış portföy doğrusal programlama ile hesaplanır:
  amaç = ½ × Maksimum Drawdown + ½ × CDaR(%95) (en kötü %5 düşüş durumlarının ortalaması;
  tek bir tarihsel olaya aşırı uyumu engeller).
  Kısıtlar: açığa satış yok, tek varlık en fazla %35, rejimdeki ortalama getiri eşit
  ağırlıklı sepetin en az yarısı (yoksa "sadece en sakin varlık" çözümüne düşerdi).
  Günün rejimi ertesi günün getirisine uygulanır (ileriye bakma yok). 60 günden az
  geçmişi olan rejimler tüm-dönem çözümüne doğru çekilir.
- Aktif hedef = onaylı rejimin portföyü (geçiş sürerken %60 onaylı / %40 aday) ×
  yapısal risk bütçesi; kalan nakit.
- Sayfada: aktif hedef tablo + grafik, 6 rejimin portföyleri ve her birinin
  örneklem içi maks. DD / getirisi (eşit ağırlıkla karşılaştırmalı), aktif rejimde
  drawdown eğrisi.
- Ana sayfadaki iki eski "Gerçek Hedef Portföy Dağılımı" tablosu kaldırıldı (sayfaya
  bağlantı var); 8 varlık taramasındaki pay sütunu yeni hedefi gösterir.
- Otonom izleyici de AYNI hedefi hesaplayıp kaydediyor (`regime_min_drawdown_portfolios`).

## 3) Doğrulama raporuna eklenenler
- **Bölüm 5:** Min-DD rejim portföyünün ÖRNEKLEM DIŞI testi. Her ~çeyrekte yalnızca
  o güne kadarki veriyle yeniden optimize edilir, ertesi gün uygulanır. Nakitli ve
  nakitsiz iki sürümü, eski hedef ve eşit ağırlıkla yan yana gösterir.
- **Bölüm 6:** Faktör bazında IC tablosu. Her makro göstergenin, modeldeki kutbuyla
  her varlığı doğru mu ters mi ittiğini gösterir (TLT'deki reel faiz sorusunun kanıtı).

## Test
- 8/8 test geçti (2 yeni: min-DD kısıtları ve örneklem içi eşit ağırlığı yenmesi,
  hedefin %100'e tamamlanması). Ana sayfa + yeni sayfa + izleyici + doğrulama sahte
  veriyle baştan sona çalıştırıldı.

---

# 2026-09-28 — v2.4: hata düzeltmeleri + gerçek veriyle doğrulama altyapısı

Bu sürüm modelin ağırlıklarına ve rejim eşiklerine DOKUNMAZ. Kanıtlanmış hataları
düzeltir ve sistemin gerçek piyasada "dipten al / tepeden sat" yapıp yapmadığını
ilk kez ölçebilen altyapıyı ekler.

## 📱 Telefondan yapman gerekenler
1. Zip'teki dosyaları repoya yükle. `backtest_summary.json` bilerek pakete konmadı
   (otonom izleyicinin canlı durumu; repodaki hali korunur).
2. GitHub → Actions → **"Macro Model Historical Validation"** → **Run workflow**
   (varsayılan 10 yıl, haftalık). Sonuç: `validation_reports/historical_validation_report.md`.
   Streamlit uygulamasında 3. sekmenin en üstünde de görünür. Her pazar kendiliğinden yenilenir.

## 🔴 Kanıtlanan hatalar (düzeltildi)
1. **Uygulama 2. sekmede çöküyordu.** `app.py` 644. satır `selected_asset_state`
   değişkenini tanımlanmadan önce kullanıyordu → `NameError`. Streamlit betiği o
   noktada durduğu için "Sürekli Makro Portföy Motoru" ve "Backtest" sekmeleri hiç
   çizilemiyordu. (Sahte Streamlit + sahte veriyle çalıştırılarak kanıtlandı; düzeltme
   sonrası uygulama baştan sona çalışıyor.)
2. **Reel faiz sinyali ters işaretliydi.** "Reel Faiz İndirgeme İvmesi (10Y TIPS)" iki
   kez ters çevriliyordu: reel faiz SERT YÜKSELDİĞİNDE skor +2.5 (olumlu), DÜŞTÜĞÜNDE
   −2.2 çıkıyordu. Bu faktör altın, NQ, SPX, BTC ve TLT için pozitif kutuplu olduğundan
   yükselen reel faiz bu varlıklarda AL yönüne itiyordu. (Sentetik backtest doğru işareti
   kullandığı için sorun orada görünmüyordu.)
3. **5Y5Y enflasyon beklentisi yanlış hesap dalına düşüyordu** ("5y5y" / "5Y5Y" büyük-küçük
   harf uyuşmazlığı) → seviye çapası yerine genel EMA-trend skoru kullanılıyordu.
4. **Eski şok rejimi kanıtsız şekilde "onaylı" kalabiliyordu.** Histerezis sayacı sadece
   aday = 0 günlerinde işliyordu; aday 0/5/0/5 diye gidip gelince eski rejim süresiz
   korunuyordu (testte 10 gün kuralına karşı 25 gün). Canlı durumda da Rejim 1
   (Stagflasyon Şoku) günlerdir "geçişte" tutuluyordu, aday rejim ise 0 ile 5 arasında
   gidip geliyordu. Artık sayaç, başka bir aday olduğu günlerde de işliyor.
5. **Dolar (DTWEXBGS) canlı uçta kördü.** FRED bu seriyi ~1 hafta geç yayımlıyor
   (canlı: DTWEX son 09-18, DXY son 09-25). İleri doldurma son ~5 günü düz yapıyor,
   5 günlük değişim z-skoru (Rejim 2'nin dolar tetikleyicisi) tam canlı uçta ~0'a
   yapışıyordu. Artık son gerçek gözlemden sonrası, gerçek zamanlı DXY getirileriyle
   (tahmini beta ile) tahmin ediliyor (`dtwex_nowcast_days` alanı kaç günün tahmin
   olduğunu gösterir). Geçmiş satırlar değişmez.
6. **Otonom izleyici ile uygulama farklı portföy gösteriyordu.** İş akışı hedef
   ağırlıkları varlık sinyali OLMADAN hesaplıyordu; uygulama sinyallerle. Faktör ve
   varlık sinyali mantığı artık tek dosyada (`asset_signal_engine.py`); uygulama, izleyici
   ve doğrulama aynı kodu kullanıyor. İzleyici artık 8 varlığın AL/SAT etiketlerini de
   kaydediyor ve etiket değişince durumu yazıyor.

## 🧪 Yeni
- `historical_validation.py` + `.github/workflows/historical_validation.yml`:
  gerçek veri (FRED halka açık CSV — anahtar gerekmez — ve Yahoo), **yayın gecikmeleri
  uygulanmış** (ICSA +4, NFCI +3, DTWEX +5 iş günü vb.), canlı sistemin AYNI koduyla
  haftalık değerlendirme. Rapor:
  1. **Tepe/Dip testi** — skorun fiyatın 1 yıllık aralığındaki konumla korelasyonu;
     zirve yakınında ve dip yakınında ortalama skor.
  2. Skorun ve her bileşenin (makro / piyasa / risk döngüsü) 20-60-120 günlük IC'si.
  3. AL / SAT etiket isabeti ve koşulsuz karşılaştırma.
  4. Rejim başlangıcı sonrası getiriler ve rejim çarpanlarının yönü.
  5. Hedef ağırlıklarla gerçek portföy testi (gerçek Sharpe, maks. düşüş, 5 bps maliyet).
- `autonomous_monitor.py`: iş akışının içindeki 400 satırlık Python artık ayrı, test
  edilebilir dosya. Workflow aksiyonları v6'ya güncellendi (Node 20 kaldırıldı), push
  çakışmalarına karşı yeniden deneme eklendi.
- `test_macro_model.py`: 6 regresyon testi (hepsi geçiyor).

## ⚠️ Karar bekleyen tasarım bulgusu (değiştirilmedi)
Varlık skorunun %35-50'si "piyasa bileşeni" = 0.70 × trend + 0.30 × **zirveye yakınlık**.
Rejim 2 (Likidite Şoku) risk varlıklarındaki satışla TEYİT ediliyor ve hisse/BTC
çarpanlarını 0.20-0.30'a indiriyor; Rejim 5 (Risk-On) ise volatilitenin 1 yılın en düşük
%30'unda olmasını istiyor. Bu üç yapı birlikte sistemi yapısal olarak **momentum takipçisi**
yapıyor: zirve yakınında AL, düşüş sonrası SAT. Rastgele (yönsüz) veride bile skor ile
1 yıllık konum arasında +0.37 … +0.60 korelasyon çıkıyor, yani bu davranış formülün
kendisinden geliyor. Gerçek veride ne kadar zarar/fayda ettiğini doğrulama raporu
gösterecek; yeniden tasarım o veriye göre yapılmalı.

## Değişmeyenler
`asset_regime_weights.py` ağırlıkları, rejim eşikleri, çarpanlar, `backtest_regimes.py`
(sentetik test; tüm şok fazları hâlâ tespit ediliyor).
