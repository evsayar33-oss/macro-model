# 2026-09-28 — v3.0: Uzun vadeli döngü motoru (dipten al-unut / tepeden sat-unut) + düşüş öncelikli, rejime uyumlu portföy

## 1) 🔄 Uzun vadeli döngü sinyali — tahvil dışındaki tüm varlıklar (`cycle_engine.py`)
- **Tepe/dip ölçüsü:** fiyatın kendi 2-3 yıllık log-ortalamasından sapması (uzun vadeli
  değer / tersine dönüş sinyali — kurumsal çapraz-varlık araştırmalarının "value" ölçüsü).
- **Bantlar kendini ayarlar:** dip = varlığın kendi geçmişindeki en ucuz %10-20'lik dilim,
  tepe = en pahalı %10-20'lik dilim (genişleyen pencere, sabit sayı yok).
- **Kurulum + tetik:** bölgeye girmek sinyali ~6 ay KURAR; dönüş teyidi gelince işler
  (dip: fiyat 50g ortalamanın üstüne çıkıp 20g getiri pozitif; tepe: tersi). Düşen
  bıçağı tutmamak / yükselen trendi erken satmamak için.
- **Al-unut / sat-unut:** karar bir sonraki uç bölgeye kadar korunur. Satış = nakde geç
  (kaldıraç, açığa satış yok). Gürültülü test döngüsünde tepelere (döngü konumu 0.96-0.99)
  ve diplere (−0.92…−1.0) çok yakın, 15 yılda sadece 7 işlem.
- **Kendini geliştiren parametre seçimi:** her varlık için 24 aday (2y/3y ortalama,
  bant genişliği, teyit, yeniden giriş kuralı) doğrulamada **her yıl yalnızca geçmiş
  veriyle** yeniden seçilir ve ertesi yıl uygulanır. Kazanan
  `validation_reports/cycle_params.json`'a yazılır; canlı sinyal onu kullanır.
- **Tahvil (TLT) hariç:** faiz modeli + trend kuralı geçerli.
- Görünüm: ana sayfada seçili varlık için "Uzun Vadeli Döngü" metriği ve tarama
  tablosunda sütun; Hedef Portföy sayfasında 8 varlık tablosu (sinyal, değer z,
  bant konumu 0=dip…100=tepe, son sinyal tarihi). İzleyici de kaydeder.

## 2) 🎯 Portföy: önce minimum düşüş, sonra maksimum getiri
- 9 strateji = {risk paritesi, risk paritesi + 200g trend, **döngü + risk paritesi**} ×
  {%10 vol hedefi, **rejime göre vol hedefi** (şok rejimlerinde %6-7, nötr %10, likidite
  rallisinde %12), **rejime göre vol + düşüş freni** (portföy zirvesinin %4 altından
  itibaren risk kademeli azalır, %12'de %25'e iner, toparlandıkça geri gelir)}.
- **Seçim kuralı (senin önceliğin):** örneklem dışı maks. düşüşü **%12 içinde** kalanlar
  arasından **en yüksek yıllık getirili** olan canlı olur; hiçbiri sığmazsa en küçük düşüşlü.
- Döngü stratejisi, varlık sinyallerinin ÖRNEKLEM DIŞI (yıllık yeniden seçilen) hâlini
  kullanarak test edilir.
- Raporda kazançlı ay ve kazançlı yıl oranları (win rate) da var.
- Canlı ağırlıklar, testte kullanılan AYNI simülatörden gelir. Seçilen strateji
  uygulamada canlı hesaplanır, diğerleri GitHub izleyicisinden okunur (CPU dostu).
- Eski rejim-LP stratejileri 28.09 gerçek testinde kaybettiği için yarıştan çıkarıldı
  (Hedef Portföy sayfasında referans tablo olarak duruyor).

## 3) Doğrulama raporu
- Bölüm 8: varlık bazında döngü sinyali (örneklem dışı yıllık getiri, maks. düşüş,
  aynı dönem al-tut, kârlı al-sat turu oranı, SAT sonrası 120 günde düşüş isabeti,
  piyasada kalma süresi, seçilen parametre).
- Bölüm 7: yeni 9 stratejilik yarış + seçim.
- Çok yıllık sinyaller için veri geçmişi 16 yıla uzatıldı.

## Test
13/13 test (yeni: döngü tepede satar/dipte alır ve az işlem yapar; tahvil döngü dışı;
düşüş freni maks. düşüşü azaltır). Ana sayfa, Hedef Portföy, izleyici ve doğrulama sahte
veriyle baştan sona çalıştı.

---

# 2026-09-28 — v2.7: sayfa hatası, CPU kısıtlaması, kanıt ağırlıklı sinyaller

## 1) "ImportError" (Hedef Portföy sayfası) — düzeltildi
Repodaki dosyalar doğruydu. Streamlit Cloud, repo güncellenince sayfayı yeniden
çalıştırıyor ama önceden içe aktarılmış yardımcı modülleri (regime_portfolio,
macro_pipeline…) bellekte ESKİ halleriyle tutuyordu. Yeni sayfa eski modülde olmayan
`STRATEGY_LABELS`'i isteyince çöktü. Artık app.py ve sayfa, diskte değişmiş her yerel
modülü bağımlılık sırasıyla otomatik yeniden yüklüyor (eski modül senaryosu
taklit edilerek test edildi).

## 2) "Your app has been throttled" (CPU kısıtlaması) — azaltıldı
- Ağır doğrusal programlama optimizasyonları (rejim portföyleri) artık uygulamada
  değil, GitHub Actions izleyicisinde (2 saatte bir) hesaplanıp `backtest_summary.json`'a
  yazılıyor; uygulama bunları okuyor. Rejim değiştiyse en fazla 6 saatte bir yerel hesap.
- Optimizasyon yolu 5 günlük bloklara toplandı (~5 kat küçük problem).
- Canlı hesaplanan stratejiler (risk paritesi) saniyeler sürer.

## 3) TLT hâlâ SAT diyordu — kanıt ağırlıklı sinyal
Gerçek veride (09:43 izleyici çalışması): TLT −50.8. Nedenleri: reel faiz son 60 günde
hızla yükseldi (değişim z = −2.0), piyasa faiz artırımı fiyatlıyor ve TLT güçlü düşüş
trendinde (piyasa bileşeni −0.75). Yani yeni mantıkla da "yükselen faiz" diyordu.
Ama 10 yıllık doğrulama TLT sinyalinin **kanıtlanmış bir öngörü gücü olmadığını**
gösteriyor (IC +0.10, t = 0.6). Kanıtı olmayan bir sinyalin güçlü SAT etiketi basması
yanlış.
- Yeni kural: skorun her bileşeni (makro / piyasa / risk döngüsü), o varlığın sonraki
  60 günlük getirisini 10 yılda ne kadar öngördüğüyle ölçeklenir:
  güvenilirlik = clip(t / 2, 0, 1). |t| ≥ 2 → tam ağırlık; ters/boş → 0.
- Doğrulama bu değerleri her pazar `validation_reports/signal_reliability.json`'a
  yazar (bu paket 28.09 gerçek raporundan hesaplanmış başlangıç dosyasını içerir).
  Doğrulamanın kendisi ağırlıksız bileşenleri ölçer (döngüsel kendini onaylama yok).
- Sonuç (gerçek bileşenlerle): TLT ≈ −11 → **NÖTR**. Altın/gümüşün makro sinyali
  10 yılda ters çalıştığı için nötre iner; BTC (t 2.5) tam güçte kalır; NQ/SPX'te
  makro korunur, ters çalışan piyasa bileşeni sıfırlanır. 10 yıllık sinyallerde
  60 günlük IC: NQ 0.13→0.22, SPX 0.08→0.14, bakır −0.12→+0.07, gümüş −0.08→+0.07
  (örneklem içi, gösterge niteliğinde).
- Tarama tablosunda yeni sütunlar: "Ham Skor" ve "Kanıt Gücü".

## Test
10/10 test; ana sayfa, Hedef Portföy sayfası (eski modül senaryosu dahil), izleyici
sahte veriyle baştan sona çalıştı.

---

# 2026-09-28 — v2.6: TLT/reel faiz düzeltmesi, sinyalde "dipten al", portföy strateji yarışı

## 1) Tahvil (TLT) neden hâlâ SAT diyordu — düzeltildi
- "Reel Faiz İndirgeme İVMESİ" adına rağmen reel faizin SEVİYESİNİ ölçüyordu. Artık
  adının söylediğini ölçüyor: 60 günlük DEĞİŞİM (düşen reel faiz = olumlu). Yükselmesi
  durmuş yüksek bir reel faiz artık "baskı" sayılmıyor.
- TLT'ye ayrı bir DEĞERLEME/TAŞIMA faktörü eklendi: reel faiz seviyesi yüksek = tahvil
  ucuz ve yüksek getirili = TLT için OLUMLU (ağırlığı reel faiz faktörüyle eşit).
- Makro bileşen doygunluğu giderildi: tanh ölçeği 0.18 → 0.45 (canlı TLT'de ham −0.55
  → −0.996'ya sıkışıyordu; bileşen fiilen sadece işaretti).
- Piyasa bileşenindeki "1 yıllık zirveye yakınlık" terimi (%30) ters çevrildi: artık
  zirveden uzak = olumlu (değer). 10 yıllık doğrulamada bu terim tüm varlıklarda
  zirvede AL / dipte SAT davranışı üretiyordu (korelasyon +0.34…+0.72) ve 1y
  diplerinden sonraki getiriler SPX/NQ/TLT/WTI/HG'de zirvelerden sonrakinden iyiydi.
- Uygulama, izleyici ve doğrulama bunun için tek motoru kullanıyor
  (`compute_factor_scores` + `compute_all_asset_signals`).

## 2) Daha iyi portföy stratejileri — örneklem dışı yarış, kazanan canlı olur
Min-drawdown portföyü + yapısal risk bütçesi (ortalama %56 nakit) düşük düşüş ama zayıf
getiri veriyordu. `regime_portfolio.py`'ye 4 kurumsal strateji eklendi; hepsi %10 yıllık
volatilite hedefiyle ölçeklenir (kaldıraç yok, kalan nakit):
1. **Risk paritesi + vol hedefi** — her varlık eşit risk taşır; düşeni alarak dengeler
   (yapısal "dipten al").
2. **Risk paritesi + 200 günlük trend filtresi** — trend altındaki varlık nakde.
3. **Rejim Calmar** — her rejimde, o rejimin geçmişinde maks. düşüşü %10'u aşmayan
   portföyler içinde en yüksek getirili olan.
4. **Rejim minimum drawdown** (önceki yöntem).
- `historical_validation.py` Bölüm 7: dördü de her hafta yalnızca o güne kadarki veriyle
  (rejim stratejileri çeyreklik yeniden optimize) ertesi gün uygulanarak yarışır.
  Sonuç `validation_reports/strategy_scores.json`'a yazılır.
- 🎯 Hedef Portföy sayfası ve otonom izleyici, **en yüksek örneklem dışı Calmar**'a
  (yıllık getiri / |maks. düşüş|) sahip stratejiyi otomatik kullanır. Her yeni
  doğrulama çalışmasında seçim güncellenir (kendini geliştiren seçim). Doğrulama
  sonucu yokken varsayılan: risk paritesi + vol hedefi.
- Sayfada: strateji yarış tablosu, tüm stratejilerin güncel ağırlıkları, aktif hedef.

## Test
- 10/10 test (yeni: tüm stratejiler %100'e tamamlanır ve kaldıraçsız; yüksek-ama-sabit
  reel faiz TLT için olumlu ve momentum cezası yok).
- Ana sayfa, Hedef Portföy sayfası, izleyici ve doğrulama sahte veriyle baştan sona çalıştı.

---

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
